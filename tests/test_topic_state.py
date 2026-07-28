from datetime import datetime, timezone
from pathlib import Path

from investment_os.judgment_kernel import evidence_fingerprint
from investment_os.source_universe_intake import SourceCandidate, write_candidates
from investment_os.topic_state import render_change_digest, update_topic_state


NOW = datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc)


def _candidate(**overrides) -> SourceCandidate:
    data: dict = {
        "item_id": "company_events:NVDA:10-Q-body",
        "lane": "company_events",
        "title": "NVDA filing body changes the margin question",
        "summary": "The filing reports a verified margin change.",
        "source": "SEC filing body",
        "source_type": "primary_filing_body_read",
        "as_of_date": "2026-07-10",
        "tickers": "NVDA",
        "source_url": "https://www.sec.gov/Archives/example-1.htm",
        "confidence": "verified",
        "next_check": "Compare the filing with the earnings call and prior guidance.",
        "kill_signal": "Downgrade if the filing is restated or the call contradicts the reading.",
        "cannot_prove": "One filing does not prove a durable trend.",
        "thesis_key": "company:NVDA:margin-quality",
        "research_question": "Did margin quality change enough to alter the research priority?",
        "thesis_impact": "weakened",
        "counter_explanation": "The change may be temporary mix rather than structural deterioration.",
        "next_primary_source": "Latest earnings call transcript and next 10-Q.",
        "evidence_status": "primary_read",
        "content_hash": "sha256:filing-v1",
        "geography": "US",
    }
    data.update(overrides)
    return SourceCandidate(**data)


def _write(tmp_path: Path, candidates: list[SourceCandidate]) -> Path:
    csv_path, _ = write_candidates(candidates, tmp_path / "candidates")
    return csv_path


def test_first_fresh_primary_read_creates_a_meaningful_research_question(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"

    changes, changes_json, changes_csv = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert state_path.exists()
    assert changes_json.exists()
    assert changes_csv.exists()
    assert len(changes) == 1
    assert changes[0].change_type == "new_question"
    assert changes[0].changed_since_last_push is True
    assert changes[0].thesis_key == "company:NVDA:margin-quality"
    assert changes[0].research_question.startswith("Did margin quality")


def test_second_identical_run_is_unchanged(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    changes, _, _ = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert len(changes) == 1
    assert changes[0].change_type == "unchanged"
    assert changes[0].changed_since_last_push is False
    assert "没有足够新的主题变化" in render_change_digest(changes)


def test_summary_reword_without_new_source_is_wording_only(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    reworded = _candidate(summary="Margin moved; the wording is different but the source is unchanged.")
    candidates_csv = _write(tmp_path, [reworded])
    changes, _, _ = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "wording_only"
    assert changes[0].changed_since_last_push is False


def test_new_primary_evidence_can_weaken_a_hypothesis(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    updated = _candidate(
        summary="The next filing confirms a second margin deterioration.",
        as_of_date="2026-07-11",
        source_url="https://www.sec.gov/Archives/example-2.htm",
        thesis_impact="weakened",
    )
    candidates_csv = _write(tmp_path, [updated])
    changes, _, _ = update_topic_state(
        candidates_csv,
        state_path,
        tmp_path / "state",
        generated_at=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
    )

    assert changes[0].change_type == "hypothesis_weakened"
    assert changes[0].changed_since_last_push is True
    assert "判断削弱" in render_change_digest(changes)


def test_form4_metadata_never_counts_as_meaningful_change(tmp_path):
    form4 = _candidate(
        item_id="primary_sec:VRT:latest_filing",
        title="VRT latest SEC filing is Form 4",
        summary="SEC submissions show a Form 4 dated 2026-07-10.",
        source_type="primary_sec_recent_filing",
        tickers="VRT",
        thesis_key="company:VRT:filing",
        source_url="https://www.sec.gov/Archives/form4.xml",
        thesis_impact="unknown",
        evidence_status="primary_metadata_only",
        research_question="Does the filing body contain a business-relevant change?",
    )
    candidates_csv = _write(tmp_path, [form4])

    changes, _, _ = update_topic_state(
        candidates_csv, tmp_path / "topic_state.json", tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "metadata_only"
    assert changes[0].changed_since_last_push is False
    assert "没有足够新的主题变化" in render_change_digest(changes)


def test_duplicate_rates_sources_collapse_to_one_research_topic(tmp_path):
    treasury_target = _candidate(
        item_id="primary_macro:treasury_yield_curve",
        lane="macro_regime",
        title="Treasury source target",
        summary="Use Treasury rates as background.",
        source="U.S. Treasury",
        source_type="primary_macro_rates",
        tickers="TLT,QQQ",
        thesis_key="macro:rates-duration",
        thesis_impact="unknown",
        evidence_status="source_target_only",
        geography="US",
        source_url="https://home.treasury.gov/interest-rates",
    )
    fred_data = _candidate(
        item_id="primary_macro:fred_yield_curve_live",
        lane="macro_regime",
        title="FRED yield curve snapshot",
        summary="2Y 4.21%, 10Y 4.56%, 30Y 5.06%.",
        source="FRED",
        source_type="primary_macro_fred_yields_live",
        tickers="TLT,QQQ",
        thesis_key="macro:rates-duration",
        thesis_impact="unknown",
        evidence_status="primary_data",
        geography="US",
        source_url="https://fred.stlouisfed.org/graph/fredgraph.csv",
    )
    candidates_csv = _write(tmp_path, [treasury_target, fred_data])

    changes, _, _ = update_topic_state(
        candidates_csv, tmp_path / "topic_state.json", tmp_path / "state", generated_at=NOW
    )

    assert len(changes) == 1
    assert changes[0].item_id == "primary_macro:fred_yield_curve_live"
    assert changes[0].thesis_key == "macro:rates-duration"
    assert changes[0].change_type == "background_only"
    assert changes[0].changed_since_last_push is False


def test_dropping_from_ranked_pool_does_not_fake_a_thesis_change(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    changes, _, _ = update_topic_state(
        empty_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert len(changes) == 1
    assert changes[0].change_type == "ranking_only"
    assert changes[0].changed_since_last_push is False


def test_long_stable_summary_does_not_become_permanent_wording_change(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate(summary="evidence " * 100)])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    changes, _, _ = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "unchanged"
    assert changes[0].changed_since_last_push is False


def test_stale_evidence_cannot_force_a_meaningful_change_with_an_impact_label(tmp_path):
    stale = _candidate(as_of_date="2025-01-01", thesis_impact="weakened")
    candidates_csv = _write(tmp_path, [stale])

    changes, _, _ = update_topic_state(
        candidates_csv, tmp_path / "topic_state.json", tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "background_only"
    assert changes[0].changed_since_last_push is False


def test_rank_gap_then_reentry_with_same_evidence_does_not_push_again(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    update_topic_state(empty_csv, state_path, tmp_path / "state", generated_at=NOW)

    changes, _, _ = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert len(changes) == 1
    assert changes[0].change_type == "unchanged"
    assert changes[0].changed_since_last_push is False


def test_same_source_with_changed_impact_is_a_meaningful_judgment_change(tmp_path):
    initial = _candidate(thesis_impact="weakened")
    candidates_csv = _write(tmp_path, [initial])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    revised = _candidate(
        summary="The same filing was read more fully and now strengthens the thesis.",
        thesis_impact="strengthened",
    )
    candidates_csv = _write(tmp_path, [revised])
    changes, _, _ = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "hypothesis_strengthened"
    assert changes[0].changed_since_last_push is True


def test_same_source_with_new_evidence_digest_can_update_without_url_churn(tmp_path):
    initial = _candidate(evidence_digest="filing-facts-v1")
    candidates_csv = _write(tmp_path, [initial])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    revised = _candidate(
        summary="The live page added a second verified margin fact.",
        evidence_digest="filing-facts-v2",
        thesis_impact="weakened",
    )
    candidates_csv = _write(tmp_path, [revised])
    changes, _, _ = update_topic_state(
        candidates_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "hypothesis_weakened"
    assert changes[0].changed_since_last_push is True


def test_same_date_body_revision_changes_evidence_fingerprint(tmp_path):
    candidates_csv = _write(tmp_path, [_candidate()])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    revised = _candidate(
        summary="The source body was revised on the same date with a changed margin fact.",
        content_hash="sha256:filing-v2",
    )
    candidates_csv = _write(tmp_path, [revised])
    changes, _, _ = update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    assert changes[0].change_type == "hypothesis_weakened"
    assert changes[0].changed_since_last_push is True


def test_observed_value_revision_changes_fingerprint_but_unchanged_value_is_idempotent():
    row = {
        "item_id": "macro:test",
        "source": "FRED",
        "source_type": "primary_macro_fred_yields_live",
        "source_url": "https://fred.example/series",
        "as_of_date": "2026-07-10",
        "evidence_status": "single_source_data",
        "observed_value": "4.25",
    }

    assert evidence_fingerprint(row) == evidence_fingerprint(dict(row))
    assert evidence_fingerprint(row) != evidence_fingerprint({**row, "observed_value": "4.30"})


def test_market_numeric_revision_is_meaningful_while_unchanged_evidence_is_idempotent(tmp_path):
    initial = _candidate(
        item_id="market_live:proxy_moves",
        lane="market_action",
        title="Market proxy move",
        summary="SPY close 620.0.",
        source="yfinance + Stooq",
        source_type="market_proxy_prices_live",
        source_url="https://finance.example/quotes",
        tickers="SPY",
        thesis_key="market:cross-asset-move",
        thesis_impact="unknown_narrowed",
        evidence_status="cross_checked_data",
        content_hash="sha256:market-v1",
        observed_value='{"SPY":{"close":620.0}}',
    )
    state_path = tmp_path / "topic_state.json"
    initial_csv = _write(tmp_path, [initial])
    update_topic_state(initial_csv, state_path, tmp_path / "state", generated_at=NOW)

    unchanged, _, _ = update_topic_state(initial_csv, state_path, tmp_path / "state", generated_at=NOW)
    revised = _candidate(
        **{
            **initial.__dict__,
            "summary": "SPY close revised to 621.5 on the same date.",
            "content_hash": "sha256:market-v2",
            "observed_value": '{"SPY":{"close":621.5}}',
        }
    )
    revised_csv = _write(tmp_path, [revised])
    changed, _, _ = update_topic_state(revised_csv, state_path, tmp_path / "state", generated_at=NOW)

    assert unchanged[0].change_type == "unchanged"
    assert unchanged[0].changed_since_last_push is False
    assert changed[0].change_type == "unknown_narrowed"
    assert changed[0].changed_since_last_push is True


def test_metadata_interlude_does_not_erase_last_meaningful_evidence(tmp_path):
    body = _candidate()
    candidates_csv = _write(tmp_path, [body])
    state_path = tmp_path / "topic_state.json"
    update_topic_state(candidates_csv, state_path, tmp_path / "state", generated_at=NOW)

    metadata = _candidate(
        item_id="primary_sec:NVDA:latest_filing",
        title="NVDA latest filing metadata",
        summary="SEC index metadata only.",
        source_type="primary_sec_recent_filing",
        evidence_status="primary_metadata_only",
        thesis_impact="unknown",
    )
    metadata_csv = _write(tmp_path, [metadata])
    metadata_changes, _, _ = update_topic_state(
        metadata_csv, state_path, tmp_path / "state", generated_at=NOW
    )
    assert metadata_changes[0].change_type == "metadata_only"

    body_csv = _write(tmp_path, [body])
    reentry_changes, _, _ = update_topic_state(
        body_csv, state_path, tmp_path / "state", generated_at=NOW
    )

    assert reentry_changes[0].change_type == "unchanged"
    assert reentry_changes[0].changed_since_last_push is False


def test_stale_status_stays_diagnostic_but_cannot_be_current_fact(tmp_path):
    stale = _candidate(
        as_of_date="2026-07-10",
        evidence_status="stale",
        thesis_impact="strengthened",
        freshness_status="stale",
    )
    candidates_csv = _write(tmp_path, [stale])
    changes, _, _ = update_topic_state(
        candidates_csv, tmp_path / "topic_state.json", tmp_path / "state", generated_at=NOW
    )
    assert changes[0].evidence_status == "stale"
    assert changes[0].changed_since_last_push is False
    assert changes[0].change_type == "background_only"


def test_source_threshold_controls_promotion_window_instead_of_hardcoded_three_days(tmp_path):
    weekend_current = _candidate(
        as_of_date="2026-07-05",
        freshness_status="current",
        freshness_threshold_days=5,
        thesis_impact="unknown_narrowed",
    )
    candidates_csv = _write(tmp_path, [weekend_current])

    changes, _, _ = update_topic_state(
        candidates_csv, tmp_path / "topic_state.json", tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "new_question"
    assert changes[0].changed_since_last_push is True


def test_explicit_stale_status_cannot_promote_even_inside_source_threshold(tmp_path):
    stale = _candidate(
        as_of_date="2026-07-10",
        freshness_status="stale",
        freshness_threshold_days=5,
        thesis_impact="unknown_narrowed",
    )
    candidates_csv = _write(tmp_path, [stale])

    changes, _, _ = update_topic_state(
        candidates_csv, tmp_path / "topic_state.json", tmp_path / "state", generated_at=NOW
    )

    assert changes[0].change_type == "background_only"
    assert changes[0].changed_since_last_push is False
