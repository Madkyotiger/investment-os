from datetime import datetime, timezone
from pathlib import Path

from investment_os.cxo_intelligence import (
    build_cxo_brief_items,
    load_profile,
    render_coverage_receipt,
    render_cxo_brief,
    scan_cxo_brief_quality,
    write_cxo_outputs,
)
from investment_os.source_universe_intake import SourceCandidate, collect_source_candidates, rank_source_candidates
from investment_os.topic_state import TopicChange

LEDGER = Path("tests/fixtures/evidence_ledger.sample.csv")
PROFILE = Path("configs/profiles.sample.yaml")


def _candidate(**overrides) -> SourceCandidate:
    data: dict = {
        "item_id": "company_events:NVDA:10-Q-body",
        "lane": "company_events",
        "title": "NVDA 10-Q 正文改变了利润率问题",
        "summary": "财报正文确认利润率发生变化。",
        "source": "SEC filing body",
        "source_type": "primary_filing_body_read",
        "as_of_date": "2026-07-10",
        "tickers": "NVDA",
        "source_url": "https://www.sec.gov/Archives/example-1.htm",
        "confidence": "verified",
        "next_check": "对照业绩会和此前指引。",
        "kill_signal": "如果财报被重述，或业绩会信息与当前解读冲突，就下调判断。",
        "cannot_prove": "单份财报不能证明趋势持续。",
        "thesis_key": "company:NVDA:margin-quality",
        "research_question": "利润率质量是否变化到足以调整研究优先级？",
        "thesis_impact": "weakened",
        "counter_explanation": "变化可能来自短期业务组合，而不是结构性恶化。",
        "next_primary_source": "最新业绩会记录和下一份 10-Q。",
        "evidence_status": "primary_read",
        "geography": "US",
    }
    data.update(overrides)
    return SourceCandidate(**data)


def _change(candidate: SourceCandidate, *, meaningful: bool = True, change_type: str = "new_question") -> TopicChange:
    return TopicChange(
        item_id=candidate.item_id,
        lane=candidate.lane,
        title=candidate.title,
        change_type=change_type,
        previous_summary="",
        latest_summary=candidate.summary,
        previous_score=0,
        latest_score=candidate.total_score,
        changed_since_last_push=meaningful,
        next_check=candidate.next_check,
        kill_signal=candidate.kill_signal,
        thesis_key=candidate.thesis_key,
        research_question=candidate.research_question,
        thesis_impact=candidate.thesis_impact,
        counter_explanation=candidate.counter_explanation,
        next_primary_source=candidate.next_primary_source,
        evidence_status=candidate.evidence_status,
        geography=candidate.geography,
        source_url=candidate.source_url,
        as_of_date=candidate.as_of_date,
        cannot_prove=candidate.cannot_prove,
    )


def test_cxo_profile_scores_relevance_and_keeps_top_items_personal():
    profile = load_profile(PROFILE, "founder_operator")
    candidates = rank_source_candidates(collect_source_candidates(LEDGER), max_items=12)
    items = build_cxo_brief_items(candidates, profile, max_items=5)

    assert items
    assert len(items) <= 5
    assert items[0].cxo_relevance >= 3
    assert any("AI" in item.candidate.title or "power" in item.candidate.title.lower() or "market" in item.candidate.title.lower() for item in items)
    assert "个人投资者" in profile.role
    assert "不代表公司决策职责" in profile.role


def test_cxo_brief_is_reader_facing_not_pipeline_facing():
    profile = load_profile(PROFILE, "founder_operator")
    candidates = rank_source_candidates(collect_source_candidates(LEDGER), max_items=12)
    items = build_cxo_brief_items(candidates, profile, max_items=5)
    brief = render_cxo_brief(items, profile)
    quality = scan_cxo_brief_quality(brief)

    assert "个人投研快扫" in brief
    assert "今天最值得你看一眼" not in brief
    assert "发生了什么" not in brief
    assert "这意味着什么" not in brief
    assert "接下来只看" not in brief
    assert "对个人投资研究" not in brief
    assert "需要继续回答的是：" not in brief
    assert "反方解释是：" not in brief
    assert "下一次重点看" not in brief
    assert "问团队" not in brief
    assert "管理判断" not in brief
    assert "覆盖回执" not in brief
    assert "CXO 今日情报" not in brief
    assert "Yield levels alone" not in brief
    assert "revenue benefited" not in brief
    assert "不是交易建议" in brief
    assert all(value == 0 for value in quality.values())


def test_cxo_outputs_are_written_with_quality_scan(tmp_path):
    profile = load_profile(PROFILE, "founder_operator")
    candidates = rank_source_candidates(collect_source_candidates(LEDGER), max_items=12)
    items = build_cxo_brief_items(candidates, profile, max_items=5)
    brief_path, ranked_path, quality_path = write_cxo_outputs(items, profile, tmp_path)

    assert brief_path.exists()
    assert ranked_path.exists()
    assert quality_path.exists()
    assert "个人投研快扫" in brief_path.read_text(encoding="utf-8")


def test_cxo_brief_can_surface_change_since_last_push():
    profile = load_profile(PROFILE, "founder_operator")
    candidate = _candidate()
    items = build_cxo_brief_items([candidate], profile, max_items=5, topic_changes=[_change(candidate)])
    brief = render_cxo_brief(items, profile, topic_changes=[_change(candidate)])

    assert "利润率质量是否变化到足以调整研究优先级？" in brief
    assert "另一个需要保留的解释是" in brief
    assert "关联到业务" not in brief
    assert "？。" not in brief
    assert all(value == 0 for value in scan_cxo_brief_quality(brief).values())


def test_cxo_item_selection_rejects_metadata_only_and_duplicate_background():
    profile = load_profile(PROFILE, "founder_operator")
    meaningful = _candidate()
    form4 = _candidate(
        item_id="primary_sec:VRT:latest_filing",
        title="VRT latest SEC filing is Form 4",
        source_type="primary_sec_recent_filing",
        tickers="VRT",
        thesis_key="company:VRT:filing",
        thesis_impact="unknown",
        evidence_status="primary_metadata_only",
    )
    rates = _candidate(
        item_id="primary_macro:fred_yield_curve_live",
        lane="macro_regime",
        title="FRED yield curve snapshot",
        source_type="primary_macro_fred_yields_live",
        tickers="TLT,QQQ",
        thesis_key="macro:rates-duration",
        thesis_impact="unknown",
        evidence_status="primary_data",
    )
    changes = [
        _change(meaningful),
        _change(form4, meaningful=False, change_type="metadata_only"),
        _change(rates, meaningful=False, change_type="background_only"),
    ]

    items = build_cxo_brief_items(
        [meaningful, form4, rates], profile, max_items=5, topic_changes=changes
    )

    assert [item.candidate.item_id for item in items] == [meaningful.item_id]


def test_no_meaningful_change_brief_stays_quiet_and_reports_us_china_coverage():
    profile = load_profile(PROFILE, "founder_operator")
    us_background = _candidate(
        item_id="primary_macro:fred_yield_curve_live",
        lane="macro_regime",
        title="FRED yield curve snapshot",
        source_type="primary_macro_fred_yields_live",
        thesis_key="macro:rates-duration",
        thesis_impact="unknown",
        evidence_status="primary_data",
        geography="US",
    )
    china_background = _candidate(
        item_id="market_action:510300",
        lane="market_action",
        title="CSI 300 market context",
        source_type="market_data",
        tickers="510300",
        thesis_key="china:market-breadth",
        thesis_impact="unknown",
        evidence_status="cross_checked_data",
        geography="China",
    )
    changes = [
        _change(us_background, meaningful=False, change_type="background_only"),
        _change(china_background, meaningful=False, change_type="background_only"),
    ]
    candidates = [us_background, china_background]
    items = build_cxo_brief_items(candidates, profile, max_items=5, topic_changes=changes)
    receipt = render_coverage_receipt(candidates, changes)
    brief = render_cxo_brief(
        items,
        profile,
        generated_at=datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc),
        topic_changes=changes,
        coverage_receipt=receipt,
    )

    assert not items
    assert "没有足够强的变化值得推送" in brief
    assert "美国已检查" not in brief
    assert "中国已检查" not in brief
    assert "覆盖回执" not in brief
    assert "没有足够强的变化" in receipt
    assert "Form 4" not in brief
    assert all(value == 0 for value in scan_cxo_brief_quality(brief).values())


def test_same_thesis_metadata_cannot_borrow_a_meaningful_body_change():
    profile = load_profile(PROFILE, "founder_operator")
    metadata = _candidate(
        item_id="primary_sec:NVDA:latest_filing",
        title="NVDA latest filing metadata",
        summary="SEC index metadata only.",
        source_type="primary_sec_recent_filing",
        evidence_status="primary_metadata_only",
    )
    body = _candidate(
        item_id="company_events:NVDA:10-Q-body",
        title="NVDA 10-Q 正文改变了利润率问题",
        evidence_status="primary_read",
    )
    items = build_cxo_brief_items(
        [metadata, body],
        profile,
        max_items=5,
        topic_changes=[_change(body)],
    )

    assert [item.candidate.item_id for item in items] == [body.item_id]


def test_cxo_quality_scan_reuses_full_decision_boundary_vocabulary():
    for unsafe in (
        "满仓",
        "清仓",
        "overweight",
        "underweight",
        "position",
        "execute",
        "execution",
        "trade",
        "trading",
    ):
        assert any(scan_cxo_brief_quality(f"建议{unsafe}").values()), unsafe
    assert scan_cxo_brief_quality("shareholder value")["decision_boundary:hold"] == 0
    assert scan_cxo_brief_quality("a strategic trade-off")["decision_boundary:trade"] == 0


def test_cxo_quality_scan_blocks_english_prose_but_allows_financial_names_and_abbreviations():
    unsafe = scan_cxo_brief_quality("Yield levels alone do not prove equity direction or sector causality")
    safe = scan_cxo_brief_quality("NVIDIA 与 AMD 的 AI GPU 收入变化")

    assert unsafe["mixed_english:prose_tokens"] > 0
    assert safe["mixed_english:prose_tokens"] == 0


def test_cxo_quality_scan_blocks_worksheet_and_template_language():
    unsafe = scan_cxo_brief_quality(
        "发生了什么\n这意味着什么\n接下来只看\n对个人投资研究：盈利。\n今天最值得你看一眼：AI。\n需要继续回答的是：利润率。反方解释是：短期组合。下一次重点看 10-Q。"
    )
    safe = scan_cxo_brief_quality(
        "# 个人投研快扫\n\n## 利润率问题被改写\n\n财报正文确认利润率发生变化。利润率质量是否变化到足以调整研究优先级？另一个需要保留的解释是短期业务组合，而不是结构性恶化。接下来用最新业绩会记录和下一份 10-Q 核验。\n"
    )

    assert unsafe["ai_style:发生了什么"] == 1
    assert unsafe["ai_style:这意味着什么"] == 1
    assert unsafe["ai_style:接下来只看"] == 1
    assert unsafe["ai_style:对个人投资研究"] == 1
    assert unsafe["ai_style:今天最值得你看一眼"] == 1
    assert unsafe["ai_style:需要继续回答的是："] == 1
    assert unsafe["ai_style:反方解释是："] == 1
    assert unsafe["ai_style:下一次重点看"] == 1
    assert all(value == 0 for value in safe.values())


def test_theme_item_id_cannot_invent_an_annual_report_claim():
    profile = load_profile(PROFILE, "founder_operator")
    candidate = _candidate(
        item_id="sector_theme_discovery:theme:memory_passives",
        lane="sector_theme_discovery",
        title="Memory/passives theme",
        summary="Only an unverified theme note is available.",
        source="unverified theme note",
        source_type="theme_evidence",
        evidence_status="secondary_cross_check",
        research_question="Is there primary evidence for this theme?",
    )
    brief = render_cxo_brief(
        [build_cxo_brief_items([candidate], profile, max_items=1)[0]],
        profile,
    )

    assert "Micron 年报已经" not in brief
    assert "DRAM/NAND" not in brief
    assert "Only an unverified theme note is available" in brief
