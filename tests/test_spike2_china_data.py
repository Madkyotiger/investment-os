from __future__ import annotations

from datetime import datetime, timezone

from investment_os.spike1_research_memo import EvidenceItem
from investment_os.spike2_china_data import (
    ChinaResearchMemo,
    ChinaSymbolConfig,
    build_china_memo,
    build_china_reconciliation_evidence,
    classify_convenience_evidence,
    parse_symbol_arg,
    render_china_memo,
)


def test_parse_symbol_arg_supports_code_type_and_name():
    cfg = parse_symbol_arg("510300:etf:沪深300ETF")

    assert cfg.symbol == "510300"
    assert cfg.asset_type == "etf"
    assert cfg.name == "沪深300ETF"


def test_china_memo_renders_evidence_gaps_without_trade_decision_language():
    memo = ChinaResearchMemo(
        symbol="510300",
        asset_type="etf",
        name="沪深300ETF",
        generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc).isoformat(),
    )
    memo.evidence = [
        EvidenceItem(
            symbol="510300",
            category="china_price",
            claim="沪深300ETF latest ETF price from AKShare Eastmoney spot feed",
            value="4.123",
            source="AKShare.fund_etf_spot_em",
            as_of_date="2026-07-03",
            freshness="fresh",
            status="ok",
        ),
        EvidenceItem(
            symbol="510300",
            category="china_data_source",
            claim="Tushare package is installed but TUSHARE_TOKEN is not configured",
            value="token_missing",
            source="tushare 1.4.29",
            as_of_date="2026-07-05",
            freshness="runtime_check",
            status="missing",
        ),
    ]
    memo.evidence_gaps = ["TUSHARE_TOKEN is missing; Tushare credentialed data not fetched."]

    report = render_china_memo([memo], generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "AKShare" in report
    assert "Tushare" in report
    assert "Evidence Ledger Extract" in report
    assert "token_missing" in report
    assert "不构成投资建议" in report
    for phrase in ["建议买入", "建议卖出", "建议持有", "建议加仓", "建议减仓", "自动下单"]:
        assert phrase not in report


def test_build_china_memo_keeps_tushare_missing_as_explicit_evidence(monkeypatch):
    def fake_akshare(cfg):
        return [
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_price",
                claim="fake AKShare price",
                value="1.23",
                source="AKShare.fake",
                as_of_date="2026-07-03",
                freshness="fresh",
                status="ok",
            )
        ], []

    def fake_tushare(cfg):
        return [
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_data_source",
                claim="Tushare package is installed but TUSHARE_TOKEN is not configured",
                value="token_missing",
                source="tushare test",
                as_of_date="2026-07-05",
                freshness="runtime_check",
                status="missing",
            )
        ], ["TUSHARE_TOKEN is missing; Tushare credentialed data not fetched."]

    monkeypatch.setattr("investment_os.spike2_china_data.fetch_akshare_etf_evidence", fake_akshare)
    monkeypatch.setattr("investment_os.spike2_china_data.fetch_tushare_status_evidence", fake_tushare)

    memo = build_china_memo(ChinaSymbolConfig(symbol="510300", asset_type="etf", name="沪深300ETF"))

    assert len(memo.evidence) == 3
    assert any(item.value == "token_missing" and item.status == "missing" for item in memo.evidence)
    assert any(item.category == "china_reconciliation" and item.value == "blocked_by_tushare_token_missing" for item in memo.evidence)
    assert "TUSHARE_TOKEN is missing; Tushare credentialed data not fetched." in memo.evidence_gaps


def test_china_reconciliation_compares_akshare_and_tushare_dates():
    cfg = ChinaSymbolConfig(symbol="000300", asset_type="index", name="沪深300指数")
    evidence, gaps = build_china_reconciliation_evidence(cfg, [
        EvidenceItem(
            symbol="000300",
            category="china_index",
            claim="latest index close",
            value="4300",
            source="AKShare.stock_zh_index_daily",
            as_of_date="2026-07-03",
            freshness="fresh",
            status="ok",
        ),
        EvidenceItem(
            symbol="000300",
            category="china_tushare",
            claim="Latest close from Tushare index_daily",
            value="4301",
            source="Tushare.index_daily",
            as_of_date="2026-07-03",
            freshness="fresh",
            status="ok",
        ),
    ])

    assert not gaps
    assert evidence[0].category == "china_reconciliation"
    assert evidence[0].value == "same_trade_date"
    assert evidence[0].status == "ok"


def test_china_reconciliation_marks_stale_source_as_partial_even_when_dates_match():
    cfg = ChinaSymbolConfig(symbol="000300", asset_type="index", name="沪深300指数")
    evidence, gaps = build_china_reconciliation_evidence(cfg, [
        EvidenceItem(
            symbol="000300",
            category="china_index",
            claim="latest index close",
            value="4300",
            source="AKShare.stock_zh_index_daily",
            as_of_date="2026-07-03",
            freshness="fresh",
            status="ok",
        ),
        EvidenceItem(
            symbol="000300",
            category="china_tushare",
            claim="Latest close from Tushare index_daily",
            value="4301",
            source="Tushare.index_daily",
            as_of_date="2026-07-03",
            freshness="stale_8d",
            status="stale",
        ),
    ])

    assert not gaps
    assert evidence[0].value == "same_trade_date"
    assert evidence[0].status == "partial"
    assert "tushare_status=stale" in evidence[0].note


def test_akshare_and_tushare_are_convenience_not_official_sources():
    items = [
        EvidenceItem(
            symbol="000300",
            category="china_index",
            claim="latest index close",
            value="4300",
            source="AKShare.stock_zh_index_daily",
            as_of_date="2026-07-03",
            freshness="fresh",
            status="ok",
        ),
        EvidenceItem(
            symbol="000300",
            category="china_tushare",
            claim="latest index close",
            value="4301",
            source="Tushare.index_daily",
            as_of_date="2026-07-03",
            freshness="fresh",
            status="ok",
        ),
    ]

    classify_convenience_evidence(items)

    assert all(item.source_authority == "convenience_secondary" for item in items)
    assert items[0].underlying_endpoint == "Sina index feed via AKShare"
    assert items[1].underlying_endpoint == "Tushare index_daily"
