#!/usr/bin/env python3
"""History, open questions and source routing for the next radar run.

The preflight is an agent input handle: accumulated meaningful thesis state and
prior coverage fields. It does not collect new market data, does not skip the six
live coverage checks, never converts a source/read failure into no_change, and
does not include the previous reader brief.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import upstream_radar
from .upstream_radar import load_objective

TZ = ZoneInfo("Asia/Shanghai")
# A deployment may set these before use.
DEFAULT_RUNS_ROOT = Path("reports/upstream-radar")
DEFAULT_DB = Path("reports/upstream-radar/radar-index.sqlite")
PREFLIGHT_SCHEMA = "investment-opportunity-preflight-v3"
DIGEST_SCHEMA = "investment-preflight-digest-v1"
SEEN_THESIS_FIELDS = (
    "item_id",
    "domain",
    "title",
    "event_time",
    "source_url",
    "evidence_status",
    "fact",
    "falsifier",
    "thesis_key",
    "publication_time",
    "observation_period",
)
PRIOR_COVERAGE_FIELDS = ("domain", "check", "status", "source_count", "sources", "source_ids", "derived_source_count")
MANUAL_AUDIT_CORRECTION = {
    "id": "2026-09-08-hormuz-no-push",
    "question": (
        "撤回全称否定「今天没有足以改变研究优先级的新信号」。"
        "能源/地缘本轮核验是否覆盖物理流量与航运中断（如霍尔木兹通航），而非仅生产者政策页？"
        "同主题新观察是否被当成重复主题压制？"
        "检索 URL 与抓取 title/body 是否同一份文件？错配是否已记为 invalid/blocked 并给出 recovered source？"
    ),
    "audit_path": "audits/2026-09-08-upstream-radar-no-push-challenge.md",
}


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".pending")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def required_coverage_checks(objective) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for domain, checks in objective.required_checks.items():
        for check in checks:
            rows.append({"domain": domain, "check": check})
    return rows


def find_last_success(runs_root: Path) -> Path | None:
    ranked: list[tuple[datetime, Path]] = []
    for receipt in runs_root.glob("*/*/output/run-receipt.json"):
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("status") != "pass":
            continue
        raw_as_of = data.get("as_of")
        try:
            as_of = datetime.fromisoformat(str(raw_as_of).replace("Z", "+00:00"))
        except ValueError:
            try:
                as_of = datetime.fromisoformat(receipt.parent.parent.name)
            except ValueError:
                continue
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=TZ)
        ranked.append((as_of, receipt.parent.parent))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[-1][1]


def _slim_theses(raw: Any, *, status: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    slim: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        item = {key: row.get(key) for key in SEEN_THESIS_FIELDS if row.get(key) not in (None, "")}
        if status:
            item["status"] = status
        if item.get("item_id") or item.get("source_url") or item.get("title"):
            slim.append(item)
    return slim


def _slim_coverage(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    slim: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        item = {key: row.get(key) for key in PRIOR_COVERAGE_FIELDS if key in row}
        if item.get("domain") and item.get("check"):
            item["prior_only"] = True
            slim.append(item)
    return slim


def _thesis_from_db(db_path: Path | None, run_dir: Path | None) -> list[dict[str, Any]]:
    if db_path is None:
        return []
    from .radar_store import open_db, readback_thesis_state

    if not db_path.is_file():
        raise ValueError("radar index missing; restore or explicitly seed historical runs before collection")
    conn = open_db(db_path)
    try:
        state = readback_thesis_state(conn)
        if not conn.execute("SELECT 1 FROM runs LIMIT 1").fetchone():
            raise ValueError("radar index empty; historical state is not established")
    finally:
        conn.close()
    projected: list[dict[str, Any]] = []
    for row in state:
        projected.append({
            "thesis_key": row.get("thesis_key"),
            "item_id": row.get("last_item_id"),
            "title": row.get("last_title"),
            "event_time": row.get("last_event_time"),
            "source_url": row.get("last_source_url"),
            "fact": row.get("last_fact"),
            "status": row.get("status"),
            "last_run_id": row.get("last_run_id"),
            "last_outcome": row.get("last_outcome"),
            "run_dir": row.get("run_dir"),
            "interpretation": (row.get("judgment") or {}).get("interpretation"),
            "next_research_action": (row.get("judgment") or {}).get("next_research_action"),
            "falsifier": (row.get("judgment") or {}).get("falsifier"),
            "counterevidence": (row.get("judgment") or {}).get("counterevidence"),
        })
    return projected


def build_preflight(
    objective,
    now: datetime,
    run_dir: Path | None,
    *,
    reason: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    checks = required_coverage_checks(objective)
    required = {
        "live_body_verification": True,
        "does_not_replace_live_body_verification": True,
        "max_age_hours": objective.max_age_hours,
        "no_item_quota": True,
        "item_cap": "none",
        "coverage_checks": checks,
        "coverage_count": len(checks),
        "coverage_status_allowed": ["checked", "checked_no_change"],
        "blocked_is_not_no_change": True,
        "source_failure_is_not_no_change": True,
        "counts_only_coverage_is_not_checked": True,
        "partial_is_not_full_read": True,
        "hash_verifies_bytes_not_truth": True,
        "same_theme_new_evidence_allowed": True,
        "falsifier_required_on_push": True,
        "advisory_boundary": objective.advisory_boundary,
        "url_title_body_identity_is_declared_not_classified": True,
    }
    base = {
        "schema_version": PREFLIGHT_SCHEMA,
        "generated_at": now.isoformat(timespec="seconds"),
        "wakeAgent": True,
        "does_not_replace_live_body_verification": True,
        "source_failure_is_not_no_change": True,
        "same_theme_new_evidence_allowed": True,
        "no_push_does_not_erase_history": True,
        "hash_verifies_bytes_not_truth": True,
        "manual_audit_correction": MANUAL_AUDIT_CORRECTION,
        "research_sources": objective.research_sources,
        "objective": objective.objective,
        "required_this_round": required,
    }
    meaningful = _thesis_from_db(db_path, run_dir)
    followups = []
    catchup_since = None
    if db_path is not None:
        from .radar_store import open_db, readback_followups, latest_success_as_of
        with open_db(db_path) as conn:
            followups = readback_followups(conn, now)
            last_success = latest_success_as_of(conn)
        if last_success and (now - last_success).total_seconds() > objective.max_age_hours * 3600:
            catchup_since = last_success.isoformat()
    base["catchup_since"] = catchup_since
    base["catchup_rule"] = "若非空，补查该时刻以来的重要变化；超过72h的入选项必须标discovery_status=catchup，不改写原发布时间。"
    base["open_followups"] = [
        {key: row.get(key) for key in ("tracking_key", "title", "thesis_key", "schema_status", "run_id", "run_dir", "status", "next_check_at", "due")}
        for row in followups
    ]
    base["due_followups"] = [row for row in followups if row["due"]]
    if run_dir is None and not meaningful:
        base.update({
            "preflight_status": "blocked",
            "reason": reason or "no prior successful run",
            "forbid_no_change_claim": True,
            "prior_run": None,
            "meaningful_thesis_state": [],
        })
        return base
    prior_run: dict[str, Any] | None = None
    if run_dir is not None:
        try:
            receipt = json.loads((run_dir / "output" / "run-receipt.json").read_text(encoding="utf-8"))
            selected = json.loads((run_dir / "output" / "selected-items.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            base.update({
                "preflight_status": "blocked",
                "reason": f"prior success artifacts unreadable: {exc}"[:300],
                "forbid_no_change_claim": True,
                "prior_run": {"run_dir": str(run_dir)},
                "meaningful_thesis_state": meaningful,
            })
            return base
        if not meaningful:
            meaningful = _slim_theses(selected, status="legacy_unverified")
        prior_coverage = _slim_coverage(receipt.get("coverage"))
        prior_run = {
            "run_dir": str(run_dir),
            "as_of": receipt.get("as_of"),
            "status": receipt.get("status"),
            "outcome": receipt.get("outcome"),
            "selected_items": receipt.get("selected_items"),
            "seen_theses": _slim_theses(selected, status="legacy_unverified" if not db_path else None),
            "prior_coverage": prior_coverage,
            "prior_coverage_is_not_this_round": True,
        }
    base.update({
        "preflight_status": "pass" if (run_dir is not None or meaningful) else "blocked",
        "prior_run": prior_run,
        "meaningful_thesis_state": meaningful,
    })
    return base


DIGEST_JUDGMENT_FIELDS = ("fact", "interpretation", "falsifier", "next_research_action", "evidence_delta")


def _clip(value: Any, limit: int) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def build_digest(manifest: dict[str, Any], manifest_path: Path, digest_sha: str) -> dict[str, Any]:
    """Compact read-first index of the full manifest (read-volume cut).

    Lossless by reference: every row keeps its exact key, the full manifest
    remains the continuity source, and nothing here replaces live verification.
    Due follow-ups keep their judgment core; non-due history is title-level only.
    """
    due = []
    for row in manifest.get("due_followups") or []:
        judgment = row.get("judgment") or {}
        item = {key: row.get(key) for key in ("tracking_key", "thesis_key", "title", "next_check_at", "review_reason", "run_dir")}
        item.update({key: _clip(judgment.get(key), 600) for key in DIGEST_JUDGMENT_FIELDS if judgment.get(key)})
        due.append(item)
    open_not_due = [
        {key: row.get(key) for key in ("tracking_key", "title", "next_check_at")}
        for row in manifest.get("open_followups") or [] if not row.get("due")
    ]
    theses = [
        {key: _clip(row.get(key), 160) for key in ("thesis_key", "title", "status", "last_run_id")}
        for row in manifest.get("meaningful_thesis_state") or []
    ]
    prior = manifest.get("prior_run") or {}
    return {
        "schema_version": DIGEST_SCHEMA,
        "generated_at": manifest.get("generated_at"),
        "full_manifest_path": str(manifest_path),
        "full_manifest_sha256": digest_sha,
        "read_rule": (
            "先读本摘要；只在需要某条旧判断全文、来源或反证时，用 search_files 按 tracking_key/thesis_key "
            "在完整 manifest 中定位后局部读取，不整份重读。摘要不替代本轮来源核验，到期问题仍逐项核验。"
        ),
        "preflight_status": manifest.get("preflight_status"),
        "catchup_since": manifest.get("catchup_since"),
        "catchup_rule": manifest.get("catchup_rule"),
        "manual_audit_correction": manifest.get("manual_audit_correction"),
        "required_this_round": manifest.get("required_this_round"),
        "research_sources": manifest.get("research_sources"),
        "due_followups": due,
        "open_not_due": open_not_due,
        "meaningful_thesis_index": theses,
        "prior_run": {
            "run_dir": prior.get("run_dir"), "as_of": prior.get("as_of"), "outcome": prior.get("outcome"),
            "selected_items": prior.get("selected_items"),
            "seen_titles": [{"item_id": t.get("item_id"), "title": t.get("title")} for t in prior.get("seen_theses") or []],
            "prior_coverage": prior.get("prior_coverage"),
            "prior_coverage_is_not_this_round": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the last-success preflight for the next radar run.")
    parser.add_argument("--config", type=Path, default=upstream_radar.DEFAULT_CONFIG)
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now", help="ISO timestamp for deterministic tests")
    parser.add_argument("--run-dir", type=Path, help="Use this prior run instead of discovering the latest pass")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now).astimezone(TZ) if args.now else datetime.now(TZ)
    try:
        objective = load_objective(args.config)
        checks = required_coverage_checks(objective)
        if not checks:
            raise RuntimeError("required coverage is empty")
        if int(objective.max_age_hours) != 72:
            raise RuntimeError(f"max_age_hours is {objective.max_age_hours}, expected 72")
        run_dir = args.run_dir if args.run_dir else find_last_success(args.runs_root)
        reason = None if run_dir else "no prior successful run under runs-root"
        db_path = None if args.no_db else args.db
        manifest = build_preflight(objective, now, run_dir, reason=reason, db_path=db_path)
        out = args.out
        if out.suffix != ".json":
            out = out / "seen-state.json"
        atomic_json(out, manifest)
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        digest_path = out.with_name("seen-state-digest.json")
        atomic_json(digest_path, build_digest(manifest, out, digest))
        prior = manifest.get("prior_run") or {}
        print(json.dumps({
            "wakeAgent": True,
            "preflight_status": manifest["preflight_status"],
            "digest_path": str(digest_path),
            "digest_read_first": True,
            "manifest_path": str(out),
            "manifest_sha256": digest,
            "seen_theses": len(prior.get("seen_theses") or []),
            "meaningful_thesis_state": len(manifest.get("meaningful_thesis_state") or []),
            "open_followups": len(manifest.get("open_followups") or []),
            "due_followups": len(manifest.get("due_followups") or []),
            "catchup_since": manifest.get("catchup_since"),
            "prior_coverage": len(prior.get("prior_coverage") or []),
            "required_coverage": manifest["required_this_round"]["coverage_count"],
            "max_age_hours": manifest["required_this_round"]["max_age_hours"],
            "no_item_quota": True,
            "does_not_replace_live_body_verification": True,
            "same_theme_new_evidence_allowed": True,
            "no_push_does_not_erase_history": True,
            "forbid_no_change_claim": manifest.get("forbid_no_change_claim", False),
        }, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({
            "wakeAgent": True,
            "preflight_status": "blocked",
            "reason": str(exc)[:300],
            "does_not_replace_live_body_verification": True,
            "forbid_no_change_claim": True,
            "source_failure_is_not_no_change": True,
        }, ensure_ascii=False, separators=(",", ":")))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
