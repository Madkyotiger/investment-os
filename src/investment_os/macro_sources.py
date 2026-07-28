from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path
from typing import Callable, Mapping

import yaml


BUNDLED_MACRO_SERIES = files("investment_os").joinpath("data", "macro_series.yaml")


@dataclass(frozen=True)
class MacroSeriesDefinition:
    series_id: str
    label: str
    cadence: str
    stale_after_days: int
    unit: str


@dataclass(frozen=True)
class MacroObservation:
    series_id: str
    label: str
    observation_date: str
    retrieved_at: str
    level: float
    change: float | None
    revision: float | None
    unit: str
    freshness_status: str
    source_url: str


def _load_macro_config(path: Path | None = None) -> dict[str, object]:
    configured = path or Path("configs/macro_series.yaml")
    source = configured if configured.is_file() else BUNDLED_MACRO_SERIES
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def load_macro_series(path: Path | None = None) -> dict[str, MacroSeriesDefinition]:
    raw = _load_macro_config(path)
    rows = raw.get("series") or {}
    if not isinstance(rows, dict):
        raise ValueError("macro config series must be a mapping")
    definitions: dict[str, MacroSeriesDefinition] = {}
    for series_id, row in rows.items():
        definitions[str(series_id)] = MacroSeriesDefinition(
            series_id=str(series_id),
            label=str(row["label"]),
            cadence=str(row["cadence"]),
            stale_after_days=int(row["stale_after_days"]),
            unit=str(row["unit"]),
        )
    return definitions


def load_market_stale_after_days(path: Path | None = None) -> int:
    raw = _load_macro_config(path)
    market = raw.get("market") or {}
    if not isinstance(market, dict):
        raise ValueError("macro config market policy must be a mapping")
    threshold = int(market.get("stale_after_days", 0))
    if threshold <= 0:
        raise ValueError("macro config market.stale_after_days must be positive")
    return threshold


def _valid_rows(series_id: str, text: str) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for row in csv.DictReader(text.splitlines()):
        raw_value = row.get(series_id)
        if raw_value in {None, "", "."}:
            continue
        try:
            rows.append((str(row.get("observation_date", "")), float(raw_value)))
        except (TypeError, ValueError):
            continue
    return rows


def observation_freshness(
    observation_date: str,
    retrieved_at: datetime,
    definition: MacroSeriesDefinition,
) -> str:
    try:
        age_days = (retrieved_at.date() - date.fromisoformat(observation_date)).days
    except ValueError:
        return "stale"
    return "current" if 0 <= age_days <= definition.stale_after_days else "stale"


def parse_latest_observation(
    series_id: str,
    text: str,
    retrieved_at: datetime,
    definition: MacroSeriesDefinition | None = None,
) -> MacroObservation:
    rows = _valid_rows(series_id, text)
    if not rows:
        raise ValueError(f"No usable observations for {series_id}")
    definition = definition or MacroSeriesDefinition(series_id, series_id, "unknown", 0, "unknown")
    observation_date, level = rows[-1]
    change = level - rows[-2][1] if len(rows) >= 2 else None
    freshness_status = observation_freshness(observation_date, retrieved_at, definition)
    return MacroObservation(
        series_id=series_id,
        label=definition.label,
        observation_date=observation_date,
        retrieved_at=retrieved_at.isoformat(),
        level=level,
        change=change,
        revision=None,
        unit=definition.unit,
        freshness_status=freshness_status,
        source_url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
    )


def _write_state(path: Path, data: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect_macro_observations(
    definitions: Mapping[str, MacroSeriesDefinition],
    *,
    fetch_text: Callable[[str], str],
    state_path: Path,
    retrieved_at: datetime,
) -> list[MacroObservation]:
    previous = {}
    if state_path.exists() and state_path.read_text(encoding="utf-8").strip():
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        previous = loaded if isinstance(loaded, dict) else {}

    observations: list[MacroObservation] = []
    for series_id, definition in definitions.items():
        observation = parse_latest_observation(
            series_id,
            fetch_text(series_id),
            retrieved_at,
            definition,
        )
        old = previous.get(series_id, {})
        revision = None
        if old.get("observation_date") == observation.observation_date:
            old_level = float(old.get("level"))
            if old_level != observation.level:
                revision = observation.level - old_level
        observations.append(
            MacroObservation(
                **{**asdict(observation), "revision": revision},
            )
        )

    next_state = dict(previous)
    next_state.update({item.series_id: asdict(item) for item in observations})
    _write_state(state_path, next_state)
    return observations
