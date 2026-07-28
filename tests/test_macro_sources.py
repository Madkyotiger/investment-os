from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from investment_os.macro_sources import (
    collect_macro_observations,
    load_macro_series,
    parse_latest_observation,
)


def test_macro_allowlist_is_explicit_and_complete():
    definitions = load_macro_series(Path("configs/macro_series.yaml"))
    assert set(definitions) == {
        "DGS2", "DGS10", "DGS30", "FEDFUNDS", "CPIAUCSL", "CPILFESL", "UNRATE", "PAYEMS", "PCEPI"
    }
    assert all(definition.cadence and definition.stale_after_days > 0 for definition in definitions.values())


def test_latest_observation_keeps_observation_date_not_retrieval_date():
    text = "observation_date,DGS10\n2026-07-06,.\n2026-07-07,4.25\n"
    observation = parse_latest_observation("DGS10", text, datetime(2026, 7, 8, tzinfo=timezone.utc))
    assert observation.observation_date == "2026-07-07"
    assert observation.retrieved_at.startswith("2026-07-08")
    assert observation.level == 4.25


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
