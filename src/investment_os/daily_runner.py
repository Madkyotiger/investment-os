from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from .cxo_intelligence import (
    build_cxo_brief_items,
    load_profile,
    render_cxo_brief,
    scan_cxo_brief_quality,
)
from .judgment_kernel import is_promotable
from .source_cache import cache_key, write_record_at
from .source_health import SourceHealthStore
from .source_universe_intake import SourceCandidate, write_candidates
from .topic_state import update_topic_state


class DailyRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyRunResult:
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


def _load_config(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise DailyRunError("daily config must be a mapping")
    if raw.get("delivery_mode", "dry-run") != "dry-run":
        raise DailyRunError("live delivery is disabled; delivery_mode must remain dry-run")
    if not raw.get("input_fixture"):
        raise DailyRunError("offline input_fixture is required")
    return raw


def _candidate_from_row(row: Mapping[str, object]) -> SourceCandidate:
    names = {field.name for field in fields(SourceCandidate)}
    values = {name: row[name] for name in names if name in row}
    return SourceCandidate(**values)


def _artifact_metadata(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"sha256": _sha256_bytes(data), "bytes": len(data)}


def run_daily(config_path: Path, out_dir: Path, *, strict: bool = False) -> DailyRunResult:
    config = _load_config(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = Path(str(config["input_fixture"]))
    profile_path = Path(str(config.get("profile_config", "configs/profiles.sample.yaml")))
    fixture_bytes = fixture_path.read_bytes()
    payload = json.loads(fixture_bytes)
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        raise DailyRunError("input fixture must contain a candidates list")
    generated_at = datetime.fromisoformat(str(payload["generated_at"]))
    candidates = [_candidate_from_row(row) for row in payload["candidates"]]
    source_errors = payload.get("source_errors", [])
    if not isinstance(source_errors, list) or any(not isinstance(error, dict) for error in source_errors):
        raise DailyRunError("source_errors must be a list of structured mappings")

    blocked = [candidate for candidate in candidates if not is_promotable(candidate.to_row())]
    if strict and (blocked or source_errors):
        raise DailyRunError(
            f"strict evidence gate failed: blocked_items={len(blocked)} source_failures={len(source_errors)}"
        )

    state_dir = out_dir / str(config.get("state_dir", "state"))
    cache_dir = out_dir / str(config.get("cache_dir", "cache"))
    state_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_health = SourceHealthStore(state_dir / "source_health.json")
    for candidate in candidates:
        record = candidate.to_row()
        write_record_at(
            cache_dir / "source-records",
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
        source_health.record_success(
            candidate.item_id,
            candidate.source_url or f"urn:item:{candidate.item_id}",
            generated_at,
            content_hash=candidate.content_hash or str(record.get("evidence_digest", "")),
        )
    for error in source_errors:
        source_health.record_failure(str(error.get("source", "unknown")), error, generated_at)

    topic_state_internal = state_dir / "topic_state.json"
    candidates_csv, _ = write_candidates(candidates, state_dir / "daily-candidates")
    changes, _, _ = update_topic_state(
        candidates_csv,
        topic_state_internal,
        state_dir,
        generated_at=generated_at,
    )
    topic_state_path = out_dir / "topic_state.json"
    _atomic_write(topic_state_path, topic_state_internal.read_text(encoding="utf-8"))

    profile = load_profile(profile_path, str(config.get("profile_id", "founder_operator")))
    items = build_cxo_brief_items(candidates, profile, max_items=5)
    brief = render_cxo_brief(items, profile, generated_at=generated_at)
    quality_failures = {key: value for key, value in scan_cxo_brief_quality(brief).items() if value}
    if quality_failures:
        raise DailyRunError(f"reader brief quality gate failed: {quality_failures}")

    input_hash = _sha256_bytes(fixture_bytes)
    run_state_path = out_dir / "run_state.json"
    previous_input_hash = ""
    if run_state_path.exists():
        previous = json.loads(run_state_path.read_text(encoding="utf-8"))
        previous_input_hash = str(previous.get("input_sha256", ""))
    input_status = "unchanged" if previous_input_hash == input_hash else ("changed" if previous_input_hash else "new")

    brief_path = out_dir / "brief.md"
    source_receipt_path = out_dir / "source_receipt.json"
    source_errors_path = out_dir / "source_errors.json"
    delivery_preview_path = out_dir / "delivery_preview.json"
    manifest_path = out_dir / "manifest.json"
    _atomic_write(brief_path, brief)
    _write_json(
        source_receipt_path,
        [
            {
                "item_id": candidate.item_id,
                "source": candidate.source,
                "source_url": candidate.source_url,
                "as_of_date": candidate.as_of_date,
                "retrieved_at": candidate.retrieved_at,
                "evidence_status": candidate.evidence_status,
                "freshness_status": candidate.freshness_status,
                "body_read_status": candidate.body_read_status,
                "content_hash": candidate.content_hash,
                "promoted": is_promotable(candidate.to_row()),
            }
            for candidate in candidates
        ],
    )
    _write_json(source_errors_path, source_errors)
    _write_json(
        run_state_path,
        {
            "generated_at": generated_at.isoformat(),
            "input_sha256": input_hash,
            "input_status": input_status,
            "meaningful_changes": sum(1 for change in changes if change.changed_since_last_push),
            "promoted_item_ids": [item.candidate.item_id for item in items],
        },
    )
    _write_json(
        delivery_preview_path,
        {
            "mode": "dry-run",
            "live_delivery_enabled": False,
            "artifact": str(brief_path),
            "message": "No Feishu, webhook, email, or scheduler action was performed.",
        },
    )

    artifacts = {
        path.name: _artifact_metadata(path)
        for path in (
            brief_path,
            source_receipt_path,
            source_errors_path,
            run_state_path,
            topic_state_path,
            delivery_preview_path,
        )
    }
    _write_json(
        manifest_path,
        {
            "generated_at": generated_at.isoformat(),
            "input_fixture": str(fixture_path),
            "input_sha256": input_hash,
            "delivery_mode": "dry-run",
            "strict": strict,
            "candidate_count": len(candidates),
            "promoted_items": len(items),
            "blocked_items": len(blocked),
            "source_failure_count": len(source_errors),
            "artifacts": artifacts,
        },
    )
    return DailyRunResult(
        brief_path=brief_path,
        manifest_path=manifest_path,
        source_receipt_path=source_receipt_path,
        source_errors_path=source_errors_path,
        run_state_path=run_state_path,
        topic_state_path=topic_state_path,
        delivery_preview_path=delivery_preview_path,
    )
