from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from investment_os.spike1_research_memo import EvidenceItem
from investment_os.spike2_china_data import (
    ChinaResearchMemo,
    ChinaSymbolConfig,
    build_china_memo,
    build_china_reconciliation_evidence,
    classify_convenience_evidence,
    fetch_tushare_status_evidence,
    parse_symbol_arg,
    render_china_memo,
    tushare_endpoint_for_asset,
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


def test_build_china_memo_keeps_tushare_optional_state_explicit(monkeypatch):
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
                claim="Tushare is an optional second source and is not configured",
                value="optional_source_not_configured",
                source="tushare test",
                as_of_date="2026-07-05",
                freshness="runtime_check",
                status="not_applicable",
            )
        ], []

    monkeypatch.setattr("investment_os.spike2_china_data.fetch_akshare_etf_evidence", fake_akshare)
    monkeypatch.setattr("investment_os.spike2_china_data.fetch_tushare_status_evidence", fake_tushare)

    memo = build_china_memo(ChinaSymbolConfig(symbol="510300", asset_type="etf", name="沪深300ETF"))

    assert len(memo.evidence) == 3
    assert any(item.value == "optional_source_not_configured" and item.status == "not_applicable" for item in memo.evidence)
    assert any(
        item.category == "china_reconciliation" and item.value == "optional_second_source_not_configured"
        for item in memo.evidence
    )
    assert memo.evidence_gaps == []


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


def test_stock_asset_uses_stock_adapter_not_etf(monkeypatch):
    calls = []

    def fake_stock(cfg):
        calls.append(("stock", cfg.symbol))
        return [], []

    def fake_etf(cfg):
        calls.append(("etf", cfg.symbol))
        return [], []

    monkeypatch.setattr("investment_os.spike2_china_data.fetch_akshare_stock_evidence", fake_stock, raising=False)
    monkeypatch.setattr("investment_os.spike2_china_data.fetch_akshare_etf_evidence", fake_etf)
    monkeypatch.setattr("investment_os.spike2_china_data.fetch_tushare_status_evidence", lambda _cfg: ([], []))

    build_china_memo(ChinaSymbolConfig(symbol="601318", asset_type="stock", name="中国平安"))

    assert calls == [("stock", "601318")]


def test_tushare_endpoint_routes_stock_without_reusing_fund_daily():
    assert tushare_endpoint_for_asset("stock") == "daily"
    assert tushare_endpoint_for_asset("equity") == "daily"
    assert tushare_endpoint_for_asset("etf") == "fund_daily"
    assert tushare_endpoint_for_asset("index") == "index_daily"
    with pytest.raises(ValueError, match="Unsupported China asset type"):
        tushare_endpoint_for_asset("bond")


def test_missing_tushare_token_is_optional_not_a_gap(monkeypatch):
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    monkeypatch.setitem(sys.modules, "tushare", SimpleNamespace(__version__="test"))

    evidence, gaps = fetch_tushare_status_evidence(ChinaSymbolConfig("601318", "stock", "中国平安"))

    assert gaps == []
    assert evidence[0].value == "optional_source_not_configured"
    assert evidence[0].status == "not_applicable"
