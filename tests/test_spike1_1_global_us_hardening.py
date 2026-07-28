from __future__ import annotations

from datetime import datetime, timezone

from investment_os.spike1_1_global_us_hardening import (
    GlobalUSResearchMemo,
    GlobalUSSymbolConfig,
    PeerFinancialProfile,
    ProxyProfile,
    _extract_item_section_bodies,
    _extract_item_sections,
    _select_theme_snippet,
    _extract_item_sections_from_chunks,
    build_macro_sector_evidence,
    build_peer_financial_evidence,
    build_peer_set_evidence,
    build_theme_filing_snippet_evidence,
    collect_peer_labels,
    parse_symbol_arg,
    render_global_us_memo,
)
from investment_os.spike1_research_memo import EvidenceItem


def test_parse_symbol_arg_supports_sector_proxy_and_name():
    cfg = parse_symbol_arg("NVDA:equity:XLK:NVIDIA")

    assert cfg.symbol == "NVDA"
    assert cfg.asset_type == "equity"
    assert cfg.sector_proxy == "XLK"
    assert cfg.name == "NVIDIA"


def test_macro_sector_evidence_uses_us_and_sector_proxies():
    cfg = GlobalUSSymbolConfig(symbol="NVDA", asset_type="equity", sector_proxy="XLK", name="NVIDIA")
    profiles = {
        "SPY": ProxyProfile("SPY", "US large-cap equity proxy", 700.0, 0.05, 0.2, "2026-07-03", "fresh", "ok"),
        "XLK": ProxyProfile("XLK", "Technology sector proxy", 300.0, 0.1, 0.3, "2026-07-03", "fresh", "ok"),
        "TLT": ProxyProfile("TLT", "US long-duration Treasury proxy", 85.0, -0.02, 0.01, "2026-07-03", "fresh", "ok"),
        "UUP": ProxyProfile("UUP", "US dollar proxy", 28.0, 0.01, -0.03, "2026-07-03", "fresh", "ok"),
    }

    evidence, gaps = build_macro_sector_evidence(cfg, profiles)

    assert not gaps
    assert {item.category for item in evidence} == {"macro_sector_context"}
    assert {item.value.split(";")[0] for item in evidence} >= {"close=700", "close=300"}
    assert {item.symbol for item in evidence} == {"NVDA"}


def test_peer_set_evidence_uses_default_peer_map_without_decision_language():
    cfg = GlobalUSSymbolConfig(symbol="NVDA", asset_type="equity", sector_proxy="XLK", name="NVIDIA")
    labels = collect_peer_labels([cfg])
    profiles = {
        "AMD": ProxyProfile("AMD", labels["AMD"], 170.0, 0.12, 0.4, "2026-07-03", "fresh", "ok"),
        "AVGO": ProxyProfile("AVGO", labels["AVGO"], 260.0, 0.08, 0.25, "2026-07-03", "fresh", "ok"),
        "TSM": ProxyProfile("TSM", labels["TSM"], 220.0, 0.1, 0.3, "2026-07-03", "fresh", "ok"),
    }

    evidence, gaps = build_peer_set_evidence(cfg, profiles)

    assert not gaps
    assert {item.category for item in evidence} == {"peer_set_context"}
    assert {item.claim for item in evidence} >= {
        "AMD peer context for NVDA",
        "AVGO peer context for NVDA",
        "TSM peer context for NVDA",
    }
    assert all("trading signal" in item.note for item in evidence)
    assert all("建议买入" not in item.note and "recommend buy" not in item.note.lower() for item in evidence)


def test_peer_financial_evidence_adds_ratio_context_without_decision_language():
    cfg = GlobalUSSymbolConfig(symbol="NVDA", asset_type="equity", sector_proxy="XLK", name="NVIDIA")
    profiles = {
        "AMD": PeerFinancialProfile(
            symbol="AMD",
            label="US equity peer for NVDA",
            as_of_date="2026-07-05",
            status="ok",
            market_cap=844_000_000_000,
            trailing_pe=172.6,
            forward_pe=39.3,
            price_to_book=13.1,
            profit_margin=0.1337,
            revenue_growth=0.378,
            debt_to_equity=6.0,
            current_ratio=2.7,
        )
    }

    evidence, gaps = build_peer_financial_evidence(cfg, profiles)

    assert any("AVGO" in gap for gap in gaps)
    assert any("TSM" in gap for gap in gaps)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.category == "peer_financial_context"
    assert item.claim == "AMD peer financial ratio context for NVDA"
    assert "trailing_pe=172.6" in item.value
    assert "profit_margin=13.37%" in item.value
    assert "not a trading signal" in item.note
    assert "recommend buy" not in item.value.lower() + item.note.lower()


def test_global_us_memo_renders_two_lane_scope_and_boundary():
    memo = GlobalUSResearchMemo(
        symbol="AAPL",
        asset_type="equity",
        sector_proxy="XLK",
        name="Apple",
        generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc).isoformat(),
        evidence=[
            EvidenceItem(
                symbol="AAPL",
                category="filing_deep_read",
                claim="10-K Item 1A section detected: Risk Factors",
                value="section_found; chars=12000",
                source="edgartools.Filing.markdown(form=10-K)",
                as_of_date="2025-10-31",
                freshness="annual_filing_section",
                status="ok",
            ),
            EvidenceItem(
                symbol="AAPL",
                category="macro_sector_context",
                claim="SPY context: US large-cap equity proxy",
                value="close=700; 60D=5.00%; 1Y=20.00%",
                source="OpenBB.equity.price.historical(provider=yfinance)",
                as_of_date="2026-07-03",
                freshness="fresh",
                status="ok",
            ),
        ],
        evidence_gaps=["Peer set not yet attached."],
        research_suggestions=[
            "建议核对价格、财务、filing、宏观/行业四类证据是否互相支持或互相冲突。",
        ],
    )

    report = render_global_us_memo([memo], generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "Global/US" in report
    assert "China branch" in report
    assert "Evidence Ledger Extract" in report
    assert "filing_deep_read" in report
    assert "不构成投资建议" in report
    for phrase in ["建议买入", "建议卖出", "建议持有", "建议加仓", "建议减仓", "目标收益", "自动下单"]:
        assert phrase not in report


def test_filing_section_extraction_uses_section_chunks_when_markdown_headings_are_missing():
    chunks = [
        "Page PART I Item 1. Business 3 Item 1A. Risk Factors 6",
        "Item 1.        Business",
        "General We seek to be useful. " * 30,
        "Competition Our businesses face many competitors. " * 30,
        "Item 1A.       Risk Factors",
        "Please carefully consider the following risk factors. " * 30,
        "Item 1B.       Unresolved Staff Comments",
        "Item 7.        Management’s Discussion and Analysis of Financial Condition and Results of Operations",
        "Overview Revenue and expenses are discussed here. " * 30,
        "Item 7A.       Quantitative and Qualitative Disclosures About Market Risk",
    ]

    sections = _extract_item_sections_from_chunks(chunks, {"1": "Business", "1A": "Risk Factors", "7": "Management Discussion and Analysis"})

    assert sections["1"][1] > 500
    assert sections["1A"][1] > 500
    assert sections["7"][1] > 500


def test_filing_section_extraction_merges_markdown_and_chunks_preferring_better_body():
    markdown = "## Item 1. Business\nShort body\n## Item 1A. Risk Factors\nShort risk"
    chunks = [
        "Item 1. Business",
        "Longer business body. " * 100,
        "Item 1A. Risk Factors",
        "Longer risk body. " * 100,
    ]

    sections = _extract_item_sections(markdown, chunks=chunks, targets={"1": "Business", "1A": "Risk Factors"})

    assert sections["1"][1] > len("Short body")
    assert sections["1A"][1] > len("Short risk")


def test_filing_section_body_extraction_preserves_source_excerpt_text():
    markdown = "## Item 1. Business\nShort body\n## Item 1A. Risk Factors\nShort risk"
    chunks = [
        "Item 1. Business",
        "We operate cloud infrastructure and software platforms for customers. " * 20,
        "Item 1A. Risk Factors",
        "Our business faces cybersecurity and regulatory risks. " * 20,
    ]

    bodies = _extract_item_section_bodies(markdown, chunks=chunks, targets={"1": "Business", "1A": "Risk Factors"})

    assert "cloud infrastructure" in bodies["1"][1]
    assert "cybersecurity" in bodies["1A"][1]
    assert len(bodies["1"][1]) > len("Short body")


def test_theme_snippet_selection_prefers_keyword_dense_source_text():
    body = (
        "Generic boilerplate statement. " * 10
        + "Revenue increased because customer demand for cloud services and platform subscriptions grew across segments. "
        + "Other administrative details followed. " * 5
    )

    snippet = _select_theme_snippet(body, ["revenue", "customer", "cloud", "segment"])

    assert "Revenue increased" in snippet
    assert "cloud services" in snippet
    assert len(snippet) <= 520


def test_theme_snippet_selection_skips_statement_table_noise():
    body = (
        "FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA INCOME STATEMENTS | Revenue | Income | Expenses | 2025 | 2024 |. "
        + "Revenue increased primarily due to cloud services demand, higher subscription usage, and improved segment mix. "
        + "Operating margin changed as infrastructure and sales expenses moved with customer demand."
    )

    snippet = _select_theme_snippet(body, ["revenue", "income", "margin", "demand", "segment"])

    assert "Revenue increased" in snippet
    assert "FINANCIAL STATEMENTS" not in snippet
    assert "|" not in snippet


def test_theme_filing_snippet_evidence_adds_three_reviewable_snippets():
    section_bodies = {
        "1": (
            "Business",
            "We design cloud platforms, subscription services, devices, and customer tools across operating segments. " * 8,
        ),
        "1A": (
            "Risk Factors",
            "Our business is subject to cybersecurity, supply chain, regulatory, and competition risks that could materially affect results. " * 8,
        ),
        "7": (
            "Management Discussion and Analysis",
            "Revenue and operating margin changed because demand, product mix, and expenses moved across reportable segments. " * 8,
        ),
    }

    evidence = build_theme_filing_snippet_evidence(
        symbol="MSFT",
        form="10-K",
        filing_date="2026-07-05",
        section_bodies=section_bodies,
        url="https://sec.example/filing",
        accession="000-test",
        cache_note="markdown_cache=hit",
    )

    assert {item.category for item in evidence} == {"filing_theme_snippet"}
    assert {item.claim for item in evidence} == {
        "10-K Item 1 theme snippet: business_model",
        "10-K Item 1A theme snippet: risk_factor",
        "10-K Item 7 theme snippet: performance_driver",
    }
    assert any("cloud platforms" in item.value for item in evidence)
    assert any("cybersecurity" in item.value for item in evidence)
    assert any("operating margin" in item.value for item in evidence)
    assert all("not an interpretation" in item.note for item in evidence)
    assert all(item.body_read_status == "read" for item in evidence)
    assert all(item.content_hash.startswith("sha256:") for item in evidence)
