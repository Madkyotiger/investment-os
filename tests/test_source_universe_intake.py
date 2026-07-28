from datetime import datetime, timezone
from pathlib import Path

from investment_os.source_universe_intake import (
    SourceCandidate,
    collect_source_candidates,
    rank_source_candidates,
    rank_with_coverage,
    write_candidates,
)
from investment_os.cxo_intelligence import build_cxo_brief_items, load_profile
from investment_os.hard_source_collectors import collect_hard_source_candidates, write_hard_source_candidates

LEDGER = Path("tests/fixtures/evidence_ledger.sample.csv")
WATCHLIST = Path("configs/watchlist.sample.yaml")


def test_source_universe_collects_cross_lane_candidates():
    candidates = collect_source_candidates(LEDGER, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc))
    lanes = {candidate.lane for candidate in candidates}

    assert "macro_regime" in lanes
    assert "company_events" in lanes
    assert "sector_theme_discovery" in lanes
    assert any(candidate.confidence in {"verified", "probable"} for candidate in candidates)
    assert all(1 <= candidate.decision_usefulness <= 5 for candidate in candidates)


def test_source_universe_ranking_prioritizes_decision_usefulness():
    candidates = collect_source_candidates(LEDGER, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc))
    ranked = rank_source_candidates(candidates, max_items=5)

    assert len(ranked) == 5
    assert ranked[0].decision_usefulness >= ranked[-1].decision_usefulness
    assert ranked[0].total_score >= ranked[-1].total_score - 5


def test_source_universe_writer_outputs_csv_and_json(tmp_path):
    candidates = rank_source_candidates(collect_source_candidates(LEDGER), max_items=3)
    csv_path, json_path = write_candidates(candidates, tmp_path)

    assert csv_path.exists()
    assert json_path.exists()
    assert "total_score" in csv_path.read_text(encoding="utf-8").splitlines()[0]


def test_source_universe_accepts_hard_source_candidates(tmp_path):
    hard_candidates = collect_hard_source_candidates(WATCHLIST, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc))
    hard_csv, _ = write_hard_source_candidates(hard_candidates, tmp_path)
    candidates = collect_source_candidates(LEDGER, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc), hard_sources_csv_path=hard_csv)

    assert any(candidate.source_type == "watchlist_config" for candidate in candidates)
    assert any(candidate.source_type.startswith("primary_macro") for candidate in candidates)
    assert any(candidate.lane == "portfolio_watchlist" for candidate in candidates)


def test_source_universe_builds_a_china_market_question_from_live_ledger():
    candidates = collect_source_candidates(
        LEDGER,
        generated_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    china = [candidate for candidate in candidates if candidate.geography == "China"]

    assert china
    assert any(candidate.source_type == "china_market_data_single_source" for candidate in china)
    assert any(candidate.thesis_key == "china:market-breadth" for candidate in china)
    assert any("Tushare" in candidate.counter_explanation for candidate in china)


def test_output_ranking_preserves_us_and_china_coverage():
    candidates = collect_source_candidates(
        LEDGER,
        generated_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    selected = rank_with_coverage(candidates, max_items=5)

    assert len(selected) == 5
    assert {candidate.geography for candidate in selected} >= {"US", "China"}


def test_market_candidate_without_completed_second_source_stays_single_source():
    candidate = SourceCandidate(
        item_id="market_live:proxy_moves",
        lane="market_action",
        title="Market move",
        summary="二源行情暂未取得；价格变化只作为待核验市场线索。",
        source="yfinance daily adjusted prices + Stooq cross-check",
        source_type="market_proxy_prices_live",
        as_of_date="2026-07-10",
        confidence="market_data_probable",
    )

    assert candidate.evidence_status == "single_source_data"


def test_market_candidate_only_becomes_cross_checked_after_confirmed_second_source():
    candidate = SourceCandidate(
        item_id="market_live:proxy_moves",
        lane="market_action",
        title="Market move",
        summary="Stooq 二源行情已覆盖当前代理资产。",
        source="yfinance daily adjusted prices + Stooq cross-check",
        source_type="market_proxy_prices_live",
        as_of_date="2026-07-10",
        confidence="market_data_cross_checked",
    )

    assert candidate.evidence_status == "cross_checked_data"


def test_single_source_market_cannot_self_declare_cross_checked_status():
    candidate = SourceCandidate(
        item_id="market_live:proxy_moves",
        lane="market_action",
        title="Market move",
        summary="二源行情暂未取得。",
        source="yfinance",
        source_type="market_proxy_prices_live",
        as_of_date="2026-07-10",
        confidence="market_data_probable",
        evidence_status="cross_checked_data",
    )

    assert candidate.evidence_status == "single_source_data"


def test_source_target_cannot_enter_reader_brief():
    candidate = SourceCandidate(
        item_id="primary_macro:treasury_target",
        lane="macro_regime",
        title="Treasury source target",
        summary="A URL to inspect later.",
        source="U.S. Treasury",
        source_type="primary_macro_rates",
        as_of_date="2026-07-10",
        source_url="https://home.treasury.gov/interest-rates",
        evidence_status="source_target_only",
    )
    items = build_cxo_brief_items([candidate], load_profile(Path("configs/profiles.sample.yaml")))
    assert items == []


def test_body_read_evidence_requires_url_and_non_empty_hash():
    missing_hash = SourceCandidate(
        item_id="filing:missing-hash",
        lane="company_events",
        title="Filing body",
        summary="Body text was allegedly read.",
        source="SEC",
        source_type="primary_filing_body_read",
        as_of_date="2026-07-10",
        source_url="https://www.sec.gov/example.htm",
        body_read_status="read",
        evidence_status="primary_body_read",
    )
    valid = SourceCandidate(
        item_id="filing:valid",
        lane="company_events",
        title="Filing body",
        summary="Body text was read.",
        source="SEC",
        source_type="primary_filing_body_read",
        as_of_date="2026-07-10",
        source_url="https://www.sec.gov/example.htm",
        body_read_status="read",
        content_hash="sha256:abc123",
        evidence_status="primary_body_read",
    )
    assert missing_hash.evidence_status == "primary_metadata_only"
    assert valid.evidence_status == "primary_body_read"


def test_missing_evidence_fields_fail_closed():
    candidate = SourceCandidate(
        item_id="unknown:evidence",
        lane="company_events",
        title="Unknown evidence",
        summary="No provenance fields.",
        source="",
        source_type="",
        as_of_date="",
        confidence="verified",
    )
    assert candidate.evidence_status == "unavailable"
