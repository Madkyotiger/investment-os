from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from investment_os.spike1_1_global_us_hardening import GlobalUSResearchMemo
from investment_os.spike1_research_memo import EvidenceItem
from investment_os.spike2_china_data import ChinaResearchMemo
from investment_os.us_china_pilot import (
    build_us_review_question_evidence,
    render_external_research_note,
    render_us_china_report,
    scan_boundary,
    scan_external_note_quality,
)


def test_us_china_report_keeps_us_first_and_china_parallel_boundary():
    generated_at = datetime(2026, 7, 5, tzinfo=timezone.utc)
    us_memo = GlobalUSResearchMemo(
        symbol="AAPL",
        asset_type="equity",
        sector_proxy="XLK",
        name="Apple",
        generated_at=generated_at.isoformat(),
        evidence=[
            EvidenceItem(
                symbol="AAPL",
                category="filing_deep_read",
                claim="10-K Item 1A section detected: Risk Factors",
                value="section_found; chars=68000",
                source="edgartools.Filing.markdown(form=10-K)",
                as_of_date="2025-10-31",
                freshness="annual_filing_section",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="peer_financial_context",
                claim="MSFT peer financial ratio context for AAPL",
                value="market_cap=2900.73B; trailing_pe=23.26; forward_pe=20.16; price_to_book=7.001; profit_margin=39.34%; revenue_growth=18.30%; debt_to_equity=30.27; current_ratio=1.283",
                source="yfinance.Ticker.info",
                as_of_date="2026-07-05",
                freshness="runtime_financial_profile",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="peer_financial_context",
                claim="AMZN peer financial ratio context for AAPL",
                value="market_cap=2610.43B; trailing_pe=31.64; forward_pe=24.51; price_to_book=5.905; profit_margin=12.22%; revenue_growth=16.60%; debt_to_equity=53.3; current_ratio=1.177",
                source="yfinance.Ticker.info",
                as_of_date="2026-07-05",
                freshness="runtime_financial_profile",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="filing_theme_snippet",
                claim="10-K Item 1A theme snippet: risk_factor",
                value="The company faces supply chain and regulatory risks that could materially affect results.",
                source="edgartools.Filing.markdown+sections(form=10-K)",
                as_of_date="2025-10-31",
                freshness="annual_filing_theme_snippet",
                status="ok",
            ),
        ],
        evidence_gaps=["Peer set not yet attached."],
    )
    us_memo.evidence.extend(build_us_review_question_evidence(us_memo))
    china_memo = ChinaResearchMemo(
        symbol="510300",
        asset_type="etf",
        name="沪深300ETF",
        generated_at=generated_at.isoformat(),
        evidence=[
            EvidenceItem(
                symbol="510300",
                category="china_data_source",
                claim="Tushare package is installed but TUSHARE_TOKEN is not configured",
                value="token_missing",
                source="tushare test",
                as_of_date="2026-07-05",
                freshness="runtime_check",
                status="missing",
            )
        ],
        evidence_gaps=["TUSHARE_TOKEN is missing; Tushare credentialed data not fetched."],
    )

    report = render_us_china_report([us_memo], [china_memo], generated_at=generated_at)

    assert "US-first Global core" in report
    assert "other global markets are deferred" in report
    assert "China market data remains active" in report
    assert "## 4. US Peer Financial Comparison" in report
    assert "MSFT" in report and "23.26" in report and "39.34%" in report
    assert "## 5. US Filing Theme Snippet Index" in report
    assert "risk_factor" in report
    assert "## 6. US Review Questions / Red-Flag Checks" in report
    assert "peer_review_question" in report
    assert "filing_review_question" in report
    assert "Red-flag question" in report
    assert "token_missing" not in report  # detailed rows live in ledger, summary keeps report compact
    assert "TUSHARE_TOKEN is missing" in report
    assert "不构成投资建议" in report
    assert all(count == 0 for count in scan_boundary(report).values())


def test_boundary_scan_catches_decision_phrases():
    result = scan_boundary("这里不应该出现：建议买入，也不能 recommend sell。")

    assert result["建议买入"] == 1
    assert result["recommend sell"] == 1


def test_us_review_question_evidence_converts_peer_and_filing_rows_without_decision_language():
    generated_at = datetime(2026, 7, 5, tzinfo=timezone.utc)
    memo = GlobalUSResearchMemo(
        symbol="AAPL",
        asset_type="equity",
        sector_proxy="XLK",
        name="Apple",
        generated_at=generated_at.isoformat(),
        evidence=[
            EvidenceItem(
                symbol="AAPL",
                category="peer_financial_context",
                claim="MSFT peer financial ratio context for AAPL",
                value="market_cap=2900.73B; trailing_pe=23.26; forward_pe=20.16; price_to_book=7.001; profit_margin=39.34%; revenue_growth=18.30%; debt_to_equity=30.27; current_ratio=1.283",
                source="yfinance.Ticker.info",
                as_of_date="2026-07-05",
                freshness="runtime_financial_profile",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="peer_financial_context",
                claim="AMZN peer financial ratio context for AAPL",
                value="market_cap=2610.43B; trailing_pe=31.64; forward_pe=24.51; price_to_book=5.905; profit_margin=12.22%; revenue_growth=16.60%; debt_to_equity=53.3; current_ratio=1.177",
                source="yfinance.Ticker.info",
                as_of_date="2026-07-05",
                freshness="runtime_financial_profile",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="filing_theme_snippet",
                claim="10-K Item 1A theme snippet: risk_factor",
                value="These laws and regulations can increase regulatory risks by requiring complex compliance measures.",
                source="edgartools.Filing.markdown+sections(form=10-K)",
                as_of_date="2025-10-31",
                freshness="annual_filing_theme_snippet",
                status="ok",
            ),
        ],
    )

    review_items = build_us_review_question_evidence(memo)
    joined = "\n".join(item.value + item.note for item in review_items)

    assert {item.category for item in review_items} == {"peer_review_question", "filing_review_question"}
    assert any("valuation_vs_quality" in item.claim for item in review_items)
    assert any("balance_sheet_comparability" in item.claim for item in review_items)
    assert any("growth_margin_quality" in item.claim for item in review_items)
    assert any("source_methodology_check" in item.claim for item in review_items)
    assert any("risk_factor" in item.claim for item in review_items)
    assert "trailing_pe range" in joined
    assert "profit_margin range" in joined
    assert "revenue_growth range" in joined
    assert "source-methodology" in joined
    assert "statement-period alignment" in joined
    assert "observable trigger" in joined
    assert all(item.value.strip().endswith("?") for item in review_items)
    assert all(count == 0 for count in scan_boundary(joined).values())


def test_external_research_note_renders_from_ledger_without_internal_leaks():
    generated_at = datetime(2026, 7, 5, tzinfo=timezone.utc)
    items = [
        EvidenceItem(
            symbol="AAPL",
            category="price",
            claim="Latest adjusted close from OpenBB yfinance provider",
            value="308.6",
            source="OpenBB.equity.price.historical(provider=yfinance)",
            as_of_date="2026-07-02",
            freshness="fresh",
            status="ok",
        ),
        EvidenceItem(
            symbol="AAPL",
            category="peer_review_question",
            claim="AAPL peer review question: source_methodology_check",
            value="Review question: Which source-methodology checks are needed before using peer ratios from yfinance.Ticker.info—statement-period alignment?",
            source="local DataOS review-rule engine from peer_financial_context",
            as_of_date="2026-07-05",
            freshness="derived_from_current_evidence",
            status="partial",
            note="info_cache=hit:.cache/investment_os/yfinance_info/example.json",
        ),
        EvidenceItem(
            symbol="AAPL",
            category="filing_review_question",
            claim="AAPL filing review question: risk_factor",
            value="Red-flag question: Using evidence basis \"supply chain risk\", what observable trigger would show it is worsening?",
            source="local DataOS review-rule engine from filing_theme_snippet",
            as_of_date="2025-10-31",
            freshness="derived_from_current_evidence",
            status="partial",
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
            note="Skeleton is ready; credentialed data fetch is intentionally blocked until token is configured.",
        ),
        EvidenceItem(
            symbol="510300",
            category="china_reconciliation",
            claim="AKShare/Tushare field reconciliation status",
            value="blocked_by_tushare_token_missing",
            source="local DataOS reconciliation gate",
            as_of_date="2026-07-05",
            freshness="runtime_check",
            status="missing",
            note="AKShare lane ran; Tushare comparison intentionally blocked until TUSHARE_TOKEN is configured.",
        ),
        EvidenceItem(
            symbol="theme:ai_infrastructure",
            category="expert_signal_context",
            claim="AI infrastructure bottlenecks may extend beyond GPUs",
            value="A public expert signal points to memory, optical networking, power, and packaging as possible constraints.",
            source="X public expert signal: @aleabitoreddit",
            as_of_date="2026-07-05",
            freshness="public_expert_signal",
            status="partial",
            url="https://x.com/aleabitoreddit/status/2073763512216899825",
            note="Evidence strength=weak; verify with supplier filings, capex disclosure, lead times, pricing, and earnings-call evidence.",
        ),
        EvidenceItem(
            symbol="theme:ai_infrastructure",
            category="expert_signal_review_question",
            claim="Which AI infrastructure bottleneck is economically material?",
            value="Which primary evidence would verify or contradict the AI infrastructure bottleneck signal before it becomes a research observation?",
            source="Evidence Ledger review-rule seed from public expert signal",
            as_of_date="2026-07-05",
            freshness="derived_from_public_signal",
            status="partial",
            note="Question only; does not support any trade decision or final investment conclusion.",
        ),
        EvidenceItem(
            symbol="theme:ai_infrastructure",
            category="expert_source_verification",
            claim="Full-stack AI data center infrastructure scope",
            value="NVIDIA describes Blackwell as data center scale infrastructure including GPUs, CPUs, DPUs, interconnects, switch chips, systems, and networking adapters.",
            source="SEC filing: NVIDIA FY2025 Form 10-K",
            as_of_date="2025-01-26",
            freshness="source_verification_verified",
            status="ok",
            url="https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
            note="Expert signal checked: AI infrastructure bottlenecks may extend beyond GPUs; Evidence direction=support; Evidence strength=verified; Cannot prove: which component is binding; Next action: map supplier capacity and pricing evidence.",
        ),
    ]

    note = render_external_research_note(items, generated_at=generated_at)
    scan = scan_external_note_quality(note)

    assert "Investment Research Note / 投研参考报告" in note
    assert "Source Freshness & Evidence Coverage" in note
    assert "Evidence-Backed Observations" in note
    assert "Public Expert Signal Crosswalk" in note
    assert "Source Verification Crosswalk" in note
    assert "auditable-source rows" in note
    assert "NVIDIA FY2025 Form 10-K" in note
    assert "not yet verified by primary evidence" in note
    assert "Research Questions / Red-Flag Checks" in note
    assert "Evidence Gaps & Source Caveats" in note
    assert "Decision Boundary" in note
    assert "TUSHARE_TOKEN is not configured" in note
    assert "Tushare credential missing" in note
    assert "token_missing" not in note
    assert "blocked_by_tushare_token_missing" not in note
    assert "local DataOS" not in note
    assert ".cache" not in note
    assert all(count == 0 for count in scan.values())


def test_external_note_quality_scan_catches_hype_and_social_pump_language():
    scan = scan_external_note_quality("这不是 external note 能说的话：10倍、韭菜、跟着机构、sure thing。")

    assert scan["hype:10倍"] == 1
    assert scan["hype:韭菜"] == 1
    assert scan["hype:跟着机构"] == 1
    assert scan["hype:sure thing"] == 1


def test_external_advisory_template_is_client_safe_and_boundary_clean():
    template_path = Path(__file__).resolve().parents[1] / "templates" / "advisory-report-template.md"
    text = template_path.read_text(encoding="utf-8")
    lower_text = text.lower()

    for marker in [
        "Investment Research Note",
        "Source Freshness & Evidence Coverage",
        "Evidence Gaps & Source Caveats",
        "Research Questions / Red-Flag Checks",
        "Decision Boundary",
        "不构成投资建议",
    ]:
        assert marker in text

    for internal_marker in ["/mnt/", "uv run", "scripts/", ".cache", "reports/us-china-pilot", "local DataOS"]:
        assert internal_marker.lower() not in lower_text

    for decision_phrase in ["买入", "卖出", "持有", "recommend buy", "recommend sell", "recommend hold", "自动下单"]:
        assert decision_phrase not in lower_text

    for hype_phrase in ["10倍", "20倍", "10x", "20x", "韭菜", "收割", "跟着机构", "确定性机会", "sure thing"]:
        assert hype_phrase.lower() not in lower_text

    assert all(count == 0 for count in scan_external_note_quality(text).values())
    assert all(count == 0 for count in scan_boundary(text).values())
