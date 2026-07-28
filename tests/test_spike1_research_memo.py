from __future__ import annotations

from datetime import datetime, timezone

from investment_os.spike1_research_memo import (
    EvidenceItem,
    SymbolResearchMemo,
    can_generate_business_implication,
    render_research_memo,
)


def test_spike1_research_memo_preserves_evidence_and_boundary():
    memo = SymbolResearchMemo(
        symbol="AAPL",
        generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc).isoformat(),
        evidence=[
            EvidenceItem(
                symbol="AAPL",
                category="fundamentals",
                claim="Latest annual revenue",
                value="416.16B",
                source="FinanceToolkit",
                as_of_date="2025",
                freshness="annual_statement",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="filing",
                claim="Latest SEC 10-K filing metadata",
                value="Apple Inc. 10-K filed 2025-10-31",
                source="edgartools.Company.get_filings",
                as_of_date="2025-10-31",
                freshness="fresh",
                status="ok",
                url="https://www.sec.gov/",
            ),
        ],
        evidence_gaps=["Macro context not yet attached in this spike."],
        research_suggestions=[
            "建议核对最新财报口径：收入、利润率、现金流和同业对比是否一致。",
            "建议形成反方 thesis：哪些宏观、行业或公司事件会推翻当前研究假设。",
        ],
    )

    report = render_research_memo([memo], generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "FinanceToolkit" in report
    assert "edgartools" in report
    assert "Evidence Ledger Extract" in report
    assert "Decision boundary" in report
    assert "不构成投资建议" in report
    for phrase in ["建议买入", "建议卖出", "建议持有", "建议加仓", "建议减仓"]:
        assert phrase not in report


def test_evidence_items_have_required_source_and_freshness_fields():
    item = EvidenceItem(
        symbol="MSFT",
        category="price",
        claim="Latest adjusted close",
        value="100.00",
        source="OpenBB.equity.price.historical(provider=yfinance)",
        as_of_date="2026-07-03",
        freshness="fresh",
        status="ok",
    )

    assert item.source
    assert item.as_of_date
    assert item.freshness
    assert item.status in {"ok", "partial", "stale", "missing"}


def test_metadata_only_filing_cannot_generate_business_implication():
    item = EvidenceItem(
        symbol="ACME",
        category="filing",
        claim="Latest SEC 10-Q filing metadata",
        value="10-Q filed",
        source="SEC submissions",
        as_of_date="2026-07-07",
        freshness="fresh",
        status="ok",
        url="https://www.sec.gov/example.htm",
        body_read_status="metadata_only",
    )

    assert can_generate_business_implication(item) is False
