from datetime import datetime, timezone

import pandas as pd

from investment_os.a_share_daily import (
    AShareSymbol,
    SourceReceipt,
    _event_evidence,
    _freshness_from_date,
    _margin_evidence,
    count_usable_symbols,
    fetch_stock_price_evidence,
    market_symbol,
    render_a_share_brief,
)
from investment_os.evidence_contract import EvidenceItem


def test_market_symbol_routes_shenzhen_shanghai_and_beijing():
    assert market_symbol("601318") == "sh601318"
    assert market_symbol("688122") == "sh688122"
    assert market_symbol("300502") == "sz300502"
    assert market_symbol("920879") == "bj920879"


def test_freshness_uses_a_share_market_date_at_utc_boundary():
    generated_at = datetime(2026, 8, 3, 16, 30, tzinfo=timezone.utc)

    assert _freshness_from_date("2026-08-04", 5, generated_at) == "fresh"


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
        generated_at=datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc),
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


def test_margin_feed_cut_at_a_page_size_is_a_source_error_not_a_missing_row():
    generated_at = datetime(2026, 11, 11, 5, 0, tzinfo=timezone.utc)
    receipt = SourceReceipt("AKShare.stock_margin_detail_sse", "ok", 2000, "2026-11-10", "official_public_data_via_adapter")
    symbol = [AShareSymbol("688981", "中芯国际")]

    def margin_rows(frame: pd.DataFrame) -> list[EvidenceItem]:
        return _margin_evidence(symbol, {"sse": frame, "szse": None}, {"sse": receipt, "szse": receipt}, generated_at)

    cut_before_symbol = pd.DataFrame({"标的证券代码": [f"{600000 + index}" for index in range(2000)]})
    complete_list = pd.DataFrame({"标的证券代码": [f"{600000 + index}" for index in range(1999)]})

    assert margin_rows(cut_before_symbol)[0].status == "source_error"
    assert margin_rows(complete_list)[0].status == "missing"


def test_price_before_the_close_uses_the_last_finished_session():
    class FakeAK:
        @staticmethod
        def stock_zh_a_hist(**_kwargs):
            return pd.DataFrame([
                {"日期": "2026-11-09", "收盘": 250.00, "成交量": 100.0, "成交额": 1000.0},
                {"日期": "2026-11-10", "收盘": 252.50, "成交量": 120.0, "成交额": 1200.0},
                {"日期": "2026-11-11", "收盘": 246.75, "成交量": 60.0, "成交额": 600.0},
            ])

    def close_row(hour_utc: int) -> EvidenceItem:
        evidence, _ = fetch_stock_price_evidence(
            AShareSymbol("300750", "宁德时代"),
            FakeAK(),
            generated_at=datetime(2026, 11, 11, hour_utc, 7, tzinfo=timezone.utc),
        )
        return next(item for item in evidence if item.category == "a_share_price")

    midday, after_close = close_row(5), close_row(8)

    assert (midday.as_of_date, midday.value) == ("2026-11-10", "252.50")
    assert (after_close.as_of_date, after_close.value) == ("2026-11-11", "246.75")


def _lhb(code: str, amount: str) -> EvidenceItem:
    return EvidenceItem(
        symbol=code,
        category="a_share_lhb",
        claim="institutional LHB activity",
        value=f"events=1;amount={amount}",
        source="AKShare.stock_lhb_jgmmtj_em",
        as_of_date="2026-08-03",
        freshness="fresh",
        status="ok",
    )


def test_direction_sentence_is_counted_from_the_evidence_and_every_symbol_is_listed():
    generated_at = datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc)
    symbols = [AShareSymbol(f"60000{index}", f"标的{index}") for index in range(6)]

    mixed = render_a_share_brief(
        symbols,
        [_lhb(symbol.code, "5000000.0" if index < 4 else "-3000000.0") for index, symbol in enumerate(symbols)],
        generated_at=generated_at,
    )
    one_sided = render_a_share_brief(symbols[:2], [_lhb(symbol.code, "5000000.0") for symbol in symbols[:2]], generated_at=generated_at)

    assert "龙虎榜机构席位有4只净买入、2只净卖出，方向不一致。" in mixed
    assert all(f"（{symbol.code}）" in mixed for symbol in symbols)
    assert "有龙虎榜机构席位数据的2只均为净买入，但上榜席位不代表全部机构。" in one_sided
    assert "没有显示机构形成一致方向" not in mixed + one_sided

