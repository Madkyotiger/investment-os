from datetime import datetime, timezone

import pandas as pd

from investment_os.a_share_daily import (
    AShareSymbol,
    SourceReceipt,
    _event_evidence,
    _margin_evidence,
    count_usable_symbols,
    fetch_stock_price_evidence,
    market_symbol,
    render_a_share_brief,
)
from investment_os.spike1_research_memo import EvidenceItem


def test_market_symbol_routes_shenzhen_shanghai_and_beijing():
    assert market_symbol("601318") == "sh601318"
    assert market_symbol("688122") == "sh688122"
    assert market_symbol("300502") == "sz300502"
    assert market_symbol("920879") == "bj920879"


def test_price_collection_falls_back_from_eastmoney_to_sina():
    class FakeAK:
        @staticmethod
        def stock_zh_a_hist(**_kwargs):
            raise RuntimeError("eastmoney unavailable")

        @staticmethod
        def stock_zh_a_daily(**_kwargs):
            return pd.DataFrame([
                {"date": "2026-07-31", "close": 54.90, "volume": 100.0, "amount": 1000.0, "turnover": 0.01},
                {"date": "2026-08-03", "close": 55.55, "volume": 160.0, "amount": 1800.0, "turnover": 0.015},
            ])

    evidence, gaps = fetch_stock_price_evidence(
        AShareSymbol("601318", "中国平安"),
        FakeAK(),
        generated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert gaps == []
    assert any(item.source == "AKShare.stock_zh_a_daily" and item.status == "ok" for item in evidence)
    assert any(item.category == "a_share_price_change" for item in evidence)
    assert next(item for item in evidence if item.category == "a_share_volume_ratio").claim == "Latest volume versus prior 1-session average"


def test_reader_brief_suppresses_pipeline_language_and_keeps_bounded_judgment():
    evidence = [
        EvidenceItem(
            symbol="601318",
            category="a_share_price_change",
            claim="daily price change",
            value="1.18%",
            source="AKShare.stock_zh_a_daily",
            as_of_date="2026-08-03",
            freshness="fresh",
            status="ok",
        ),
        EvidenceItem(
            symbol="601318",
            category="a_share_lhb",
            claim="institutional LHB activity",
            value="no_event",
            source="AKShare.stock_lhb_jgmmtj_em",
            as_of_date="2026-08-03",
            freshness="fresh",
            status="no_event",
        ),
    ]

    brief = render_a_share_brief(
        [AShareSymbol("601318", "中国平安")],
        evidence,
        generated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert "今天的判断" in brief
    assert "没有足够强的机构行为信号" in brief
    assert "不是交易建议" in brief
    assert len(brief) <= 1200
    for marker in ["source_error", "Evidence Ledger", "AKShare", "status", "接口", "测试"]:
        assert marker not in brief


def test_missing_lhb_amount_never_invents_buy_or_sell_direction():
    generated_at = datetime(2026, 8, 3, tzinfo=timezone.utc)
    symbol = AShareSymbol("601318", "中国平安")
    frame = pd.DataFrame([
        {"代码": "601318", "上榜日期": "2026-08-03", "机构买入净额": None},
    ])
    receipt = SourceReceipt(
        source="AKShare.stock_lhb_jgmmtj_em",
        status="ok",
        rows=1,
        as_of_date="2026-08-03",
        authority="convenience_secondary",
    )

    rows = _event_evidence(
        [symbol],
        frame,
        receipt,
        category="a_share_lhb",
        code_columns=("代码",),
        date_columns=("上榜日期",),
        amount_columns=("机构买入净额",),
        generated_at=generated_at,
        value_label="Institutional LHB activity",
    )
    brief = render_a_share_brief([symbol], rows, generated_at=generated_at)

    assert rows[0].status == "partial"
    assert rows[0].value == "events=1;amount=n/a"
    assert "金额字段不可用" in brief
    assert "净买入" not in brief
    assert "净卖出" not in brief


def test_no_event_and_source_error_remain_distinct():
    generated_at = datetime(2026, 8, 3, tzinfo=timezone.utc)
    symbol = AShareSymbol("601318", "中国平安")
    ok_receipt = SourceReceipt("lhb", "ok", 1, "2026-08-03", "convenience_secondary")
    error_receipt = SourceReceipt("lhb", "source_error", 0, "2026-08-03", "convenience_secondary", "timeout")
    kwargs = {
        "category": "a_share_lhb",
        "code_columns": ("代码",),
        "date_columns": ("上榜日期",),
        "amount_columns": ("机构买入净额",),
        "generated_at": generated_at,
        "value_label": "Institutional LHB activity",
    }

    no_event = _event_evidence(
        [symbol],
        pd.DataFrame([{"代码": "000001", "上榜日期": "2026-08-03", "机构买入净额": 1.0}]),
        ok_receipt,
        **kwargs,
    )
    source_error = _event_evidence([symbol], None, error_receipt, **kwargs)

    assert no_event[0].status == "no_event"
    assert source_error[0].status == "source_error"


def test_stale_price_is_not_counted_as_usable():
    symbol = AShareSymbol("601318", "中国平安")
    stale = EvidenceItem(
        symbol=symbol.code,
        category="a_share_price",
        claim="Latest A-share close",
        value="55.55",
        source="AKShare.stock_zh_a_daily",
        as_of_date="2026-07-14",
        freshness="stale_20d",
        status="stale",
    )
    assert count_usable_symbols([symbol], [stale]) == 0


def test_beijing_symbol_is_not_routed_to_shanghai_or_shenzhen_margin():
    generated_at = datetime(2026, 8, 3, tzinfo=timezone.utc)
    rows = _margin_evidence(
        [AShareSymbol("920001", "北交所样例")],
        {"sse": pd.DataFrame(), "szse": pd.DataFrame()},
        {
            "sse": SourceReceipt("sse", "ok", 0, "2026-08-03", "official_public_data"),
            "szse": SourceReceipt("szse", "ok", 0, "2026-08-03", "official_public_data"),
        },
        generated_at,
    )
    assert rows[0].status == "not_applicable"
    assert rows[0].source == "SSE/SZSE margin-detail feeds"
