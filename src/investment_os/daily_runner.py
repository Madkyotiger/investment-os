from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from .cxo_intelligence import build_cxo_brief_items, load_profile, render_cxo_brief, scan_cxo_brief_quality
from .hard_source_collectors import (
    HardSourceCandidate,
    collect_hard_source_candidates,
    get_last_source_errors,
)
from .judgment_kernel import is_promotable
from .source_cache import cache_key, write_record_at
from .source_universe_intake import SourceCandidate, write_candidates
from .topic_state import update_topic_state


OFFLINE_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "daily_brief_sources.json"


class DailyRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyRunResult:
    status: str
    brief_path: Path
    manifest_path: Path
    source_receipt_path: Path
    source_errors_path: Path
    run_state_path: Path
    topic_state_path: Path
    delivery_preview_path: Path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_json(path: Path, payload: object) -> None:
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _validate_inputs(watchlist_path: Path, profile_path: Path) -> None:
    for label, path in (("watchlist", watchlist_path), ("profile", profile_path)):
        if not path.is_file():
            raise DailyRunError(f"{label} file not found: {path}")


def _candidate_from_row(row: Mapping[str, object]) -> SourceCandidate:
    names = {field.name for field in fields(SourceCandidate)}
    values = {name: row[name] for name in names if name in row}
    try:
        return SourceCandidate(**values)
    except (TypeError, ValueError) as error:
        raise DailyRunError(f"invalid source candidate: {error}") from error


def _source_candidate(candidate: HardSourceCandidate | SourceCandidate) -> SourceCandidate:
    if isinstance(candidate, SourceCandidate):
        return candidate
    return _candidate_from_row(asdict(candidate))


def _load_offline_candidates() -> tuple[datetime, list[SourceCandidate], list[dict[str, object]], bytes]:
    try:
        fixture_bytes = OFFLINE_FIXTURE.read_bytes()
        payload = json.loads(fixture_bytes)
        generated_at = datetime.fromisoformat(str(payload["generated_at"]))
        rows = payload["candidates"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise DailyRunError(f"invalid offline fixture: {error}") from error
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DailyRunError("offline fixture candidates must be a list of mappings")
    errors = payload.get("source_errors", [])
    if not isinstance(errors, list) or any(not isinstance(error, dict) for error in errors):
        raise DailyRunError("offline fixture source_errors must be a list of mappings")
    return generated_at, [_candidate_from_row(row) for row in rows], errors, fixture_bytes


def _structured_errors(
    candidates: Sequence[SourceCandidate],
    collector_errors: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    errors = [dict(error) for error in collector_errors]
    for candidate in candidates:
        errors.extend(dict(error) for error in candidate.source_errors)
    unique: dict[str, dict[str, object]] = {}
    for error in errors:
        key = json.dumps(error, ensure_ascii=False, sort_keys=True, default=str)
        unique.setdefault(key, error)
    return list(unique.values())


def _collect(
    watchlist_path: Path,
    *,
    offline: bool,
) -> tuple[datetime, list[SourceCandidate], list[dict[str, object]], str]:
    if offline:
        generated_at, candidates, errors, fixture_bytes = _load_offline_candidates()
        return generated_at, candidates, errors, _sha256_bytes(fixture_bytes)
    generated_at = datetime.now(timezone.utc)
    try:
        raw_candidates = collect_hard_source_candidates(watchlist_path, generated_at=generated_at)
    except Exception as error:
        raise DailyRunError(f"live collection failed closed: {type(error).__name__}") from error
    candidates = [_source_candidate(candidate) for candidate in raw_candidates]
    errors = _structured_errors(candidates, get_last_source_errors())
    fingerprint = _sha256_bytes(
        json.dumps([candidate.to_row() for candidate in candidates], sort_keys=True, default=str).encode("utf-8")
    )
    return generated_at, candidates, errors, fingerprint


def _artifact_metadata(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"sha256": _sha256_bytes(data), "bytes": len(data)}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        _atomic_write(path, "")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _prepare_state_copy(state_path: Path, work_dir: Path) -> Path:
    temporary_state = work_dir / "topic_state.next.json"
    if state_path.exists():
        try:
            json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DailyRunError(f"invalid topic state: {error}") from error
        shutil.copyfile(state_path, temporary_state)
    return temporary_state


def _source_successes(candidates: Sequence[SourceCandidate]) -> list[dict[str, str]]:
    successes: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if not is_promotable(candidate.to_row()) or candidate.freshness_status == "stale":
            continue
        key = candidate.source_url or candidate.source
        successes.setdefault(
            key,
            {
                "source": candidate.source,
                "source_url": candidate.source_url,
                "retrieved_at": candidate.retrieved_at,
            },
        )
    return list(successes.values())


def _write_source_cache(out_dir: Path, candidates: Sequence[SourceCandidate], generated_at: datetime) -> None:
    for candidate in candidates:
        write_record_at(
            out_dir / "cache" / "source-records",
            cache_key(candidate.source_url or candidate.item_id),
            {
                "item_id": candidate.item_id,
                "retrieved_at": candidate.retrieved_at,
                "evidence_status": candidate.evidence_status,
                "content_hash": candidate.content_hash,
            },
            source_url=candidate.source_url or f"urn:item:{candidate.item_id}",
            retrieved_at=generated_at,
        )


def run_daily(
    watchlist_path: Path,
    profile_path: Path,
    state_path: Path,
    out_dir: Path,
    *,
    strict: bool = False,
    offline: bool = False,
) -> DailyRunResult:
    """Collect, validate, update durable topic state, and write one completed local run."""
    _validate_inputs(watchlist_path, profile_path)
    generated_at, candidates, source_errors, input_hash = _collect(watchlist_path, offline=offline)
    blocked = [candidate for candidate in candidates if not is_promotable(candidate.to_row())]
    source_successes = _source_successes(candidates)
    if strict and not offline and not source_successes:
        raise DailyRunError("strict live run failed: no usable live source succeeded")

    out_dir.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="investment-os-daily-", dir=state_path.parent) as temporary:
        work_dir = Path(temporary)
        temporary_state = _prepare_state_copy(state_path, work_dir)
        candidates_csv, _ = write_candidates(candidates, work_dir / "candidates")
        changes, _, _ = update_topic_state(
            candidates_csv,
            temporary_state,
            work_dir / "changes",
            generated_at=generated_at,
        )

        profile = load_profile(profile_path)
        items = build_cxo_brief_items(candidates, profile, max_items=5, topic_changes=changes)
        status = "completed" if items else "quiet"
        brief = render_cxo_brief(items, profile, generated_at=generated_at, topic_changes=changes)
        quality_failures = {key: value for key, value in scan_cxo_brief_quality(brief).items() if value}
        if quality_failures:
            raise DailyRunError(f"reader brief quality gate failed: {quality_failures}")

        brief_path = out_dir / "cxo_daily_brief.md"
        source_receipt_path = out_dir / "source_receipt.json"
        source_errors_path = out_dir / "source_errors.json"
        run_state_path = out_dir / "run_state.json"
        topic_changes_path = out_dir / "topic_changes.json"
        topic_changes_csv_path = out_dir / "topic_changes.csv"
        delivery_preview_path = out_dir / "delivery_preview.json"
        manifest_path = out_dir / "manifest.json"

        _atomic_write(brief_path, brief)
        _write_json(
            source_receipt_path,
            [
                {
                    "item_id": candidate.item_id,
                    "source": candidate.source,
                    "source_type": candidate.source_type,
                    "source_url": candidate.source_url,
                    "as_of_date": candidate.as_of_date,
                    "retrieved_at": candidate.retrieved_at,
                    "evidence_status": candidate.evidence_status,
                    "freshness_status": candidate.freshness_status,
                    "body_read_status": candidate.body_read_status,
                    "content_hash": candidate.content_hash,
                    "promotable": is_promotable(candidate.to_row()),
                    "promoted": any(item.candidate.item_id == candidate.item_id for item in items),
                }
                for candidate in candidates
            ],
        )
        _write_json(source_errors_path, source_errors)
        _write_json(topic_changes_path, [change.to_row() for change in changes])
        _write_csv(topic_changes_csv_path, [change.to_row() for change in changes])
        _write_json(
            run_state_path,
            {
                "generated_at": generated_at.isoformat(),
                "result": status,
                "input_sha256": input_hash,
                "meaningful_changes": sum(change.changed_since_last_push for change in changes),
                "promoted_item_ids": [item.candidate.item_id for item in items],
            },
        )
        _write_json(
            delivery_preview_path,
            {
                "mode": "not_requested",
                "live_delivery_enabled": False,
                "artifact": str(brief_path),
                "message": "Daily collection never sends messages; use the separate deliver command.",
            },
        )
        _write_source_cache(out_dir, candidates, generated_at)

        os.replace(temporary_state, state_path)
        topic_state_path = state_path
        artifacts = {
            path.name: _artifact_metadata(path)
            for path in (
                brief_path,
                source_receipt_path,
                source_errors_path,
                run_state_path,
                topic_changes_path,
                topic_changes_csv_path,
                delivery_preview_path,
            )
        }
        _write_json(
            manifest_path,
            {
                "schema_version": 1,
                "run_complete": True,
                "result": status,
                "mode": "offline" if offline else "live",
                "generated_at": generated_at.isoformat(),
                "watchlist": str(watchlist_path),
                "profile": str(profile_path),
                "topic_state": str(state_path),
                "strict": strict,
                "candidate_count": len(candidates),
                "promoted_items": len(items),
                "blocked_items": len(blocked),
                "usable_live_sources": 0 if offline else len(source_successes),
                "source_successes": source_successes,
                "source_failure_count": len(source_errors),
                "source_failures": source_errors,
                "artifacts": artifacts,
            },
        )

    return DailyRunResult(
        status=status,
        brief_path=brief_path,
        manifest_path=manifest_path,
        source_receipt_path=source_receipt_path,
        source_errors_path=source_errors_path,
        run_state_path=run_state_path,
        topic_state_path=topic_state_path,
        delivery_preview_path=delivery_preview_path,
    )