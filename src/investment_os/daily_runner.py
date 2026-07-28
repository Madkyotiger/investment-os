from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Mapping, Sequence

from .cxo_intelligence import build_cxo_brief_items, load_profile, render_cxo_brief, scan_cxo_brief_quality
from .hard_source_collectors import (
    HardSourceCandidate,
    collect_hard_source_candidates,
    get_last_source_errors,
)
from .judgment_kernel import is_fresh, is_promotable
from .source_cache import cache_key, write_record_at
from .source_health import SourceHealthStore
from .source_universe_intake import SourceCandidate, write_candidates
from .topic_state import update_topic_state


OFFLINE_FIXTURE = files("investment_os").joinpath("data", "daily_brief_sources.json")


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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_json(path: Path, payload: object) -> None:
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_durable_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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
    macro_state_path: Path | None = None,
) -> tuple[datetime, list[SourceCandidate], list[dict[str, object]], str]:
    if offline:
        generated_at, candidates, errors, fixture_bytes = _load_offline_candidates()
        return generated_at, candidates, errors, _sha256_bytes(fixture_bytes)
    generated_at = datetime.now(timezone.utc)
    try:
        raw_candidates = collect_hard_source_candidates(
            watchlist_path,
            generated_at=generated_at,
            macro_state_path=macro_state_path,
        )
    except Exception as error:
        raise DailyRunError(f"live collection failed closed: {type(error).__name__}") from error
    candidates = [_source_candidate(candidate) for candidate in raw_candidates]
    retrieved_at = generated_at.isoformat()
    for candidate in candidates:
        if not candidate.retrieved_at:
            candidate.retrieved_at = retrieved_at
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


def _state_journal_path(state_path: Path) -> Path:
    return state_path.with_name(f".{state_path.name}.pending.json")


def _run_fault_injection(_point: str) -> None:
    """No-op seam used by deterministic crash-recovery tests."""


def _commit_pending_state(state_path: Path, journal_path: Path) -> None:
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        manifest_path = Path(str(journal["manifest_path"]))
        expected_manifest_hash = str(journal["manifest_sha256"])
        state_records = journal.get("states")
        if not isinstance(state_records, list):
            raise TypeError("states must be a list")
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise DailyRunError("pending topic-state commit journal is invalid") from error

    if not manifest_path.is_file():
        journal_path.unlink(missing_ok=True)
        return
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise DailyRunError("pending topic-state manifest is invalid") from error
    if _sha256_bytes(manifest_bytes) != expected_manifest_hash:
        journal_path.unlink(missing_ok=True)
        return
    if manifest.get("run_complete") is not True:
        raise DailyRunError("pending topic-state manifest is not a completed run receipt")
    manifest_artifacts = manifest.get("artifacts")
    if not isinstance(manifest_artifacts, dict):
        raise DailyRunError("pending topic-state manifest artifacts are invalid")
    for name, metadata in manifest_artifacts.items():
        if not isinstance(name, str) or not isinstance(metadata, dict):
            raise DailyRunError("pending topic-state manifest artifact is invalid")
        artifact_path = manifest_path.parent / name
        try:
            artifact_bytes = artifact_path.read_bytes()
        except OSError as error:
            raise DailyRunError("pending topic-state run artifact is unavailable") from error
        if (
            _sha256_bytes(artifact_bytes) != str(metadata.get("sha256", ""))
            or len(artifact_bytes) != int(metadata.get("bytes", -1))
        ):
            raise DailyRunError("pending topic-state run artifact mismatch")
    pending_writes: list[tuple[Path, bytes]] = []
    for record in state_records:
        if not isinstance(record, dict):
            raise DailyRunError("pending state record is invalid")
        target_path = Path(str(record.get("target_path", "")))
        staged_state_path = Path(str(record.get("staged_state_path", "")))
        expected_hash = str(record.get("state_sha256", ""))
        artifact = (manifest.get("artifacts") or {}).get(staged_state_path.name)
        if not isinstance(artifact, dict) or str(artifact.get("sha256", "")) != expected_hash:
            raise DailyRunError("pending topic-state receipt does not match staged state")
        try:
            state_bytes = staged_state_path.read_bytes()
        except OSError as error:
            raise DailyRunError("pending topic-state artifact is unavailable") from error
        if _sha256_bytes(state_bytes) != expected_hash:
            raise DailyRunError("pending topic-state artifact hash mismatch")
        pending_writes.append((target_path, state_bytes))
    for target_path, state_bytes in pending_writes:
        _atomic_write_bytes(target_path, state_bytes)
    journal_path.unlink(missing_ok=True)


def _recover_pending_state(state_path: Path) -> None:
    journal_path = _state_journal_path(state_path)
    if journal_path.exists():
        _commit_pending_state(state_path, journal_path)


def _source_successes(candidates: Sequence[SourceCandidate], generated_at: datetime) -> list[dict[str, str]]:
    successes: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if (
            not is_promotable(candidate.to_row())
            or candidate.freshness_status == "stale"
            or not is_fresh(candidate.to_row(), generated_at)
        ):
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
                "observed_value": candidate.observed_value,
            },
            source_url=candidate.source_url or f"urn:item:{candidate.item_id}",
            retrieved_at=generated_at,
        )


def _companion_state_path(state_path: Path, suffix: str) -> Path:
    return state_path.with_name(f"{state_path.stem}.{suffix}.json")


def _copy_or_initialize(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        shutil.copyfile(source, destination)
    else:
        _atomic_write(destination, "{}\n")


def _source_health_key(value: str, *, source_url: str = "", item_id: str = "") -> str:
    lowered = value.lower()
    for marker, key in (
        ("fred", "fred"),
        ("sec.gov", "sec"),
        ("sec ", "sec"),
        ("yahoo", "market_yahoo"),
        ("yfinance", "market_yahoo"),
        ("stooq", "market_stooq"),
    ):
        if marker in lowered:
            base = key
            break
    else:
        base = "_".join(lowered.replace("://", "_").split())[:80] or "unknown_source"
    granular = source_url or item_id
    normalized = "_".join(
        granular.lower().replace("://", "_").replace("/", "_").replace("?", "_").replace("&", "_").split()
    )
    return f"{base}:{normalized[:120]}" if normalized else base


def _update_source_health(
    store: SourceHealthStore,
    candidates: Sequence[SourceCandidate],
    source_errors: Sequence[Mapping[str, object]],
    generated_at: datetime,
) -> None:
    for candidate in candidates:
        if candidate.evidence_status in {"source_target_only", "unavailable"}:
            continue
        method = (
            store.record_success
            if candidate.freshness_status != "stale" and is_fresh(candidate.to_row(), generated_at)
            else store.record_observation
        )
        method(
            _source_health_key(
                candidate.source,
                source_url=candidate.source_url,
                item_id=candidate.item_id,
            ),
            candidate.source_url,
            generated_at,
            content_hash=candidate.content_hash,
            as_of_date=candidate.as_of_date,
            freshness_status=candidate.freshness_status,
            freshness_threshold_days=candidate.freshness_threshold_days,
            evidence_status=candidate.evidence_status,
        )
    for error in source_errors:
        source_name = str(error.get("source") or error.get("source_url") or "unknown_source")
        store.record_failure(
            _source_health_key(source_name, source_url=str(error.get("source_url", ""))),
            error,
            generated_at,
        )


def _source_health_diagnostics(store: SourceHealthStore, generated_at: datetime) -> dict[str, dict[str, object]]:
    diagnostics = store.all()
    for record in diagnostics.values():
        last_known_good = record.get("last_known_good")
        if not isinstance(last_known_good, dict):
            record["last_known_good_status"] = "unavailable"
            continue
        try:
            threshold = int(last_known_good.get("freshness_threshold_days") or 0)
            as_of = date.fromisoformat(str(last_known_good.get("as_of_date", ""))[:10])
            age_days = (generated_at.date() - as_of).days
            current = (
                str(last_known_good.get("freshness_status", "")).lower() != "stale"
                and threshold > 0
                and 0 <= age_days <= threshold
            )
        except (TypeError, ValueError):
            current = False
        record["last_known_good_status"] = "current" if current else "stale"
        record["last_known_good_label"] = "current_last_known_good" if current else "stale_last_known_good"
        record["promoted_as_current"] = False
    return diagnostics


def _publish_run_directory(staged_dir: Path, out_dir: Path) -> None:
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if out_dir.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.previous.", dir=out_dir.parent))
        backup.rmdir()
        os.replace(out_dir, backup)
    try:
        os.replace(staged_dir, out_dir)
        _fsync_directory(out_dir.parent)
    except Exception:
        if backup is not None and backup.exists() and not out_dir.exists():
            os.replace(backup, out_dir)
        raise
    if backup is not None and backup.exists():
        shutil.rmtree(backup)


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
    state_path.parent.mkdir(parents=True, exist_ok=True)
    _recover_pending_state(state_path)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    macro_state_path = _companion_state_path(state_path, "macro")
    health_state_path = _companion_state_path(state_path, "source-health")
    with tempfile.TemporaryDirectory(prefix="investment-os-daily-", dir=out_dir.parent) as temporary:
        work_dir = Path(temporary)
        staged_run_dir = work_dir / "published-run"
        staged_run_dir.mkdir()
        temporary_state = _prepare_state_copy(state_path, work_dir)
        temporary_macro_state = work_dir / "macro-state.next.json"
        temporary_health_state = work_dir / "source-health.next.json"
        if not offline:
            _copy_or_initialize(macro_state_path, temporary_macro_state)
            _copy_or_initialize(health_state_path, temporary_health_state)

        generated_at, candidates, source_errors, input_hash = _collect(
            watchlist_path,
            offline=offline,
            macro_state_path=None if offline else temporary_macro_state,
        )
        blocked = [candidate for candidate in candidates if not is_promotable(candidate.to_row())]
        source_successes = _source_successes(candidates, generated_at)
        source_health: dict[str, dict[str, object]] = {}
        if not offline:
            health_store = SourceHealthStore(temporary_health_state)
            _update_source_health(health_store, candidates, source_errors, generated_at)
            source_health = _source_health_diagnostics(health_store, generated_at)
        if strict and not offline and not source_successes:
            _atomic_write_bytes(health_state_path, temporary_health_state.read_bytes())
            raise DailyRunError("strict live run failed: no usable live source succeeded")

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

        brief_path = staged_run_dir / "cxo_daily_brief.md"
        source_receipt_path = staged_run_dir / "source_receipt.json"
        source_errors_path = staged_run_dir / "source_errors.json"
        source_health_path = staged_run_dir / "source_health.json"
        run_state_path = staged_run_dir / "run_state.json"
        topic_changes_path = staged_run_dir / "topic_changes.json"
        topic_changes_csv_path = staged_run_dir / "topic_changes.csv"
        delivery_preview_path = staged_run_dir / "delivery_preview.json"
        staged_state_path = staged_run_dir / "topic_state.next.json"
        staged_macro_state_path = staged_run_dir / "macro_state.next.json"
        staged_health_state_path = staged_run_dir / "source_health.next.json"
        manifest_path = staged_run_dir / "manifest.json"

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
                    "freshness_threshold_days": candidate.freshness_threshold_days,
                    "body_read_status": candidate.body_read_status,
                    "content_hash": candidate.content_hash,
                    "observed_value": candidate.observed_value,
                    "revision": candidate.revision,
                    "promotable": is_promotable(candidate.to_row()),
                    "promoted": any(item.candidate.item_id == candidate.item_id for item in items),
                }
                for candidate in candidates
            ],
        )
        _write_json(source_errors_path, source_errors)
        _write_json(source_health_path, source_health)
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
                "artifact": str(out_dir / brief_path.name),
                "message": "Daily collection never sends messages; use the separate deliver command.",
            },
        )
        _write_source_cache(staged_run_dir, candidates, generated_at)
        _atomic_write_bytes(staged_state_path, temporary_state.read_bytes())
        state_artifacts = [(state_path, staged_state_path)]
        if not offline:
            _atomic_write_bytes(staged_macro_state_path, temporary_macro_state.read_bytes())
            _atomic_write_bytes(staged_health_state_path, temporary_health_state.read_bytes())
            state_artifacts.extend(
                [
                    (macro_state_path, staged_macro_state_path),
                    (health_state_path, staged_health_state_path),
                ]
            )
        artifact_paths = [
            brief_path,
            source_receipt_path,
            source_errors_path,
            source_health_path,
            run_state_path,
            topic_changes_path,
            topic_changes_csv_path,
            delivery_preview_path,
            *(artifact for _target, artifact in state_artifacts),
        ]
        artifacts = {path.name: _artifact_metadata(path) for path in artifact_paths}
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
                "source_health": source_health,
                "source_health_state": str(health_state_path) if not offline else "",
                "macro_state": str(macro_state_path) if not offline else "",
                "artifacts": artifacts,
            },
        )
        final_state_artifacts = [
            (target, out_dir / artifact.name)
            for target, artifact in state_artifacts
        ]
        journal_path = _state_journal_path(state_path)
        _write_durable_json(
            journal_path,
            {
                "schema_version": 2,
                "manifest_path": str((out_dir / manifest_path.name).resolve()),
                "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
                "states": [
                    {
                        "target_path": str(target.resolve()),
                        "staged_state_path": str(artifact.resolve()),
                        "state_sha256": str(artifacts[artifact.name]["sha256"]),
                    }
                    for target, artifact in final_state_artifacts
                ],
            },
        )
        _run_fault_injection("journal_created")
        _publish_run_directory(staged_run_dir, out_dir)
        _run_fault_injection("post_publication")

        brief_path = out_dir / brief_path.name
        source_receipt_path = out_dir / source_receipt_path.name
        source_errors_path = out_dir / source_errors_path.name
        run_state_path = out_dir / run_state_path.name
        delivery_preview_path = out_dir / delivery_preview_path.name
        manifest_path = out_dir / manifest_path.name
        _run_fault_injection("pre_state_commit")
        _commit_pending_state(state_path, journal_path)
        topic_state_path = state_path

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