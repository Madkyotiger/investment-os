from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from investment_os.hard_source_collectors import collect_fred_macro_candidates, collect_hard_source_candidates
from investment_os.judgment_kernel import classify_change, is_promotable
from investment_os.macro_sources import (
    collect_macro_observations,
    load_macro_series,
    observation_freshness,
    parse_latest_observation,
)


def test_macro_allowlist_is_explicit_and_complete():
    definitions = load_macro_series(Path("configs/macro_series.yaml"))
    assert set(definitions) == {
        "DGS2", "DGS10", "DGS30", "FEDFUNDS", "CPIAUCSL", "CPILFESL", "UNRATE", "PAYEMS", "PCEPI"
    }
    assert all(
        definition.cadence
        and definition.stale_after_days > 0
        and definition.material_change_threshold > 0
        for definition in definitions.values()
    )


def test_latest_observation_keeps_observation_date_not_retrieval_date():
    text = "observation_date,DGS10\n2026-07-06,.\n2026-07-07,4.25\n"
    observation = parse_latest_observation("DGS10", text, datetime(2026, 7, 8, tzinfo=timezone.utc))
    assert observation.observation_date == "2026-07-07"
    assert observation.retrieved_at.startswith("2026-07-08")
    assert observation.level == 4.25


def test_bundled_macro_config_preserves_materiality_thresholds_outside_checkout(monkeypatch, tmp_path):
    checkout = load_macro_series(Path("configs/macro_series.yaml"))
    monkeypatch.chdir(tmp_path)
    bundled = load_macro_series()

    assert bundled == checkout


def test_pce_release_is_still_current_on_the_day_it_is_published():
    # A month's PCE price index is published near the end of the following month:
    # September (observation date 2026-09-01) arrives around 2026-10-30.
    definition = load_macro_series(Path("configs/macro_series.yaml"))["PCEPI"]

    assert observation_freshness("2026-09-01", datetime(2026, 10, 30, tzinfo=timezone.utc), definition) == "current"


def test_macro_config_rejects_nonpositive_materiality_threshold(tmp_path):
    config = tmp_path / "macro.yaml"
    config.write_text(
        """series:
  DGS10:
    label: 10Y Treasury Yield
    cadence: business_daily
    stale_after_days: 4
    unit: percent
    material_change_threshold: 0
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="material_change_threshold"):
        load_macro_series(config)


def test_macro_collection_separates_level_change_and_revision(tmp_path):
    state = tmp_path / "macro-state.json"
    first = {
        "DGS10": "observation_date,DGS10\n2026-07-06,4.20\n2026-07-07,4.25\n",
    }
    observations = collect_macro_observations(
        {"DGS10": load_macro_series(Path("configs/macro_series.yaml"))["DGS10"]},
        fetch_text=lambda series_id: first[series_id],
        state_path=state,
        retrieved_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
    )
    assert observations[0].level == 4.25
    assert observations[0].change == pytest.approx(0.05)
    assert observations[0].revision is None

    revised = {"DGS10": "observation_date,DGS10\n2026-07-06,4.20\n2026-07-07,4.30\n"}
    observations = collect_macro_observations(
        {"DGS10": load_macro_series(Path("configs/macro_series.yaml"))["DGS10"]},
        fetch_text=lambda series_id: revised[series_id],
        state_path=state,
        retrieved_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )
    assert observations[0].revision == pytest.approx(0.05)
    assert observations[0].observation_date == "2026-07-07"


def test_macro_state_contains_no_consensus_or_surprise_claim(tmp_path):
    state = tmp_path / "macro-state.json"
    definitions = {"UNRATE": load_macro_series(Path("configs/macro_series.yaml"))["UNRATE"]}
    collect_macro_observations(
        definitions,
        fetch_text=lambda _series: "observation_date,UNRATE\n2026-06-01,4.1\n",
        state_path=state,
        retrieved_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
    )
    text = state.read_text(encoding="utf-8").lower()
    assert "surprise" not in text
    assert "consensus" not in text
    assert list(csv.DictReader("observation_date,UNRATE\n2026-06-01,4.1\n".splitlines()))
    assert json.loads(state.read_text(encoding="utf-8"))["UNRATE"]["observation_date"] == "2026-06-01"


def test_daily_macro_candidates_cover_allowlist_and_hash_same_date_revisions(monkeypatch, tmp_path):
    definitions = load_macro_series(Path("configs/macro_series.yaml"))
    values = {series_id: 4.0 + index for index, series_id in enumerate(definitions)}

    def fake_text(series_id: str) -> str:
        value = values[series_id]
        return f"observation_date,{series_id}\n2026-07-06,{value - 0.1}\n2026-07-07,{value}\n"

    monkeypatch.setattr("investment_os.hard_source_collectors._fred_series_text", fake_text)
    state_path = tmp_path / "macro-state.json"
    first = collect_fred_macro_candidates(datetime(2026, 7, 8, tzinfo=timezone.utc), state_path=state_path)
    first_by_series = {candidate.item_id.rsplit(":", 1)[-1]: candidate for candidate in first}

    values["UNRATE"] += 0.2
    second = collect_fred_macro_candidates(datetime(2026, 7, 8, tzinfo=timezone.utc), state_path=state_path)
    second_by_series = {candidate.item_id.rsplit(":", 1)[-1]: candidate for candidate in second}

    assert set(first_by_series) == set(definitions)
    assert first_by_series["UNRATE"].content_hash != second_by_series["UNRATE"].content_hash
    assert json.loads(second_by_series["UNRATE"].observed_value)["level"] == pytest.approx(values["UNRATE"])
    text = " ".join(candidate.summary.lower() for candidate in second)
    assert "consensus" not in text
    assert "surprise" not in text
    assert all(
        candidate.freshness_threshold_days == definitions[series_id].stale_after_days
        for series_id, candidate in second_by_series.items()
    )


def test_subthreshold_macro_change_is_retained_but_not_promoted(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_series_text",
        lambda series_id: f"observation_date,{series_id}\n2026-07-06,4.0\n2026-07-07,4.000001\n",
    )

    candidate = next(
        row
        for row in collect_fred_macro_candidates(
            datetime(2026, 7, 8, tzinfo=timezone.utc),
            state_path=tmp_path / "macro-state.json",
        )
        if row.item_id.endswith(":DGS10")
    )

    assert candidate.evidence_change == 1
    assert candidate.thesis_impact == "unknown"
    assert not classify_change(
        None,
        candidate.to_row(),
        datetime(2026, 7, 8, tzinfo=timezone.utc),
    ).meaningful_change


def test_material_macro_change_meets_series_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_series_text",
        lambda series_id: f"observation_date,{series_id}\n2026-07-06,4.0\n2026-07-07,4.05\n",
    )

    candidate = next(
        row
        for row in collect_fred_macro_candidates(
            datetime(2026, 7, 8, tzinfo=timezone.utc),
            state_path=tmp_path / "macro-state.json",
        )
        if row.item_id.endswith(":DGS10")
    )

    assert candidate.evidence_change == 4
    assert candidate.thesis_impact == "unknown_narrowed"
    assert is_promotable(candidate.to_row())
    assert classify_change(
        None,
        candidate.to_row(),
        datetime(2026, 7, 8, tzinfo=timezone.utc),
    ).meaningful_change


def test_material_revision_promotes_when_latest_interval_change_is_small(monkeypatch, tmp_path):
    current_level = {"value": 4.0}

    def fake_series_text(series_id: str) -> str:
        return (
            f"observation_date,{series_id}\n"
            "2026-07-06,5.0\n"
            f"2026-07-07,{current_level['value']}\n"
        )

    monkeypatch.setattr("investment_os.hard_source_collectors._fred_series_text", fake_series_text)
    state_path = tmp_path / "macro-state.json"
    collect_fred_macro_candidates(datetime(2026, 7, 8, tzinfo=timezone.utc), state_path=state_path)

    current_level["value"] = 5.01
    candidates = collect_fred_macro_candidates(
        datetime(2026, 7, 8, 1, tzinfo=timezone.utc),
        state_path=state_path,
    )
    candidate = next(row for row in candidates if row.item_id == "primary_macro:fred:DGS10")
    observed = json.loads(candidate.observed_value)

    assert observed["change"] == pytest.approx(0.01)
    assert observed["revision"] == pytest.approx(1.01)
    assert candidate.revision == pytest.approx(1.01)
    assert candidate.evidence_change == 4
    assert candidate.thesis_impact == "unknown_narrowed"
    assert classify_change(
        None,
        candidate.to_row(),
        datetime(2026, 7, 8, tzinfo=timezone.utc),
    ).meaningful_change


def test_hard_source_daily_path_uses_full_revision_aware_macro_pipeline(monkeypatch, tmp_path):
    definitions = load_macro_series(Path("configs/macro_series.yaml"))
    monkeypatch.setattr("investment_os.hard_source_collectors._safe_sec_recent", lambda: {})
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: {})
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_series_text",
        lambda series_id: f"observation_date,{series_id}\n2026-07-07,4.0\n",
    )

    candidates = collect_hard_source_candidates(
        Path("configs/watchlist.sample.yaml"),
        generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc),
        macro_state_path=tmp_path / "macro-state.json",
    )
    macro = [candidate for candidate in candidates if candidate.source_type == "primary_macro_fred_live"]

    assert {candidate.item_id.rsplit(":", 1)[-1] for candidate in macro} == set(definitions)
    assert (tmp_path / "macro-state.json").exists()


def test_monthly_series_stay_current_until_the_next_release():
    # October payrolls (observation date 2026-10-01) are published in early November and remain
    # the latest figure until early December.
    definition = load_macro_series(Path("configs/macro_series.yaml"))["PAYEMS"]

    assert observation_freshness("2026-10-01", datetime(2026, 12, 3, tzinfo=timezone.utc), definition) == "current"
    assert observation_freshness("2026-10-01", datetime(2027, 1, 15, tzinfo=timezone.utc), definition) == "stale"


def test_a_same_date_revision_is_flagged_once_and_not_again(tmp_path):
    state = tmp_path / "macro-state.json"
    definition = {"DGS10": load_macro_series(Path("configs/macro_series.yaml"))["DGS10"]}

    def revisions(levels: list[str]) -> list[float | None]:
        seen = []
        for day, level in enumerate(levels, start=8):
            text = f"observation_date,DGS10\n2026-07-06,4.20\n2026-07-07,{level}\n"
            seen.append(collect_macro_observations(
                definition, fetch_text=lambda _series, text=text: text, state_path=state,
                retrieved_at=datetime(2026, 7, day, tzinfo=timezone.utc),
            )[0].revision)
        return seen

    first, revised, repeat = revisions(["4.25", "4.30", "4.30"])
    assert first is None and revised == pytest.approx(0.05) and repeat is None
