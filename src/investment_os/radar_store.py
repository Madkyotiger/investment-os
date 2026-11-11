"""Project-local SQLite index for upstream radar runs.

Files keep source bytes. This DB stores hashes, paths, inclusion, and
longitudinal thesis metadata. A hash verifies captured bytes, not truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
SCHEMA_STATUS_VERIFIED = "verified"
FOLLOWUP_STALE_DAYS = 14  # no new selected evidence for this long: stop requiring review
FOLLOWUP_MAX_DAYS = 45  # hard cap even with a later scheduled node
SCHEMA_STATUS_LEGACY = "legacy_unverified"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  as_of TEXT NOT NULL,
  status TEXT NOT NULL,
  outcome TEXT NOT NULL,
  run_dir TEXT,
  packet_sha256 TEXT,
  schema_status TEXT NOT NULL DEFAULT 'verified',
  ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  url TEXT,
  requested_url TEXT,
  captured_title TEXT,
  kind TEXT NOT NULL,
  access_completeness TEXT,
  identity_status TEXT,
  sha256 TEXT,
  body_path TEXT,
  captured_at TEXT,
  accessed_at TEXT,
  publication_time TEXT,
  publication_time_precision TEXT,
  event_time TEXT,
  event_time_precision TEXT,
  observation_period TEXT,
  recovered_source_id TEXT,
  quote TEXT,
  PRIMARY KEY (run_id, source_id)
);
CREATE TABLE IF NOT EXISTS locators (
  locator_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  url TEXT,
  discovered_at TEXT,
  note TEXT,
  PRIMARY KEY (run_id, locator_id)
);
CREATE TABLE IF NOT EXISTS candidates (
  item_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  domain TEXT,
  title TEXT,
  thesis_key TEXT,
  inclusion TEXT NOT NULL,
  reasons TEXT,
  source_id TEXT,
  event_time TEXT,
  publication_time TEXT,
  observation_period TEXT,
  impact_score INTEGER,
  fact TEXT,
  judgment_json TEXT,
  PRIMARY KEY (run_id, item_id)
);
CREATE TABLE IF NOT EXISTS thesis_state (
  thesis_key TEXT PRIMARY KEY,
  last_run_id TEXT,
  last_event_time TEXT,
  last_item_id TEXT,
  last_title TEXT,
  last_source_url TEXT,
  last_fact TEXT,
  last_outcome TEXT,
  status TEXT NOT NULL,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS followup_reviews (
  tracking_key TEXT NOT NULL,
  run_id TEXT NOT NULL,
  status TEXT NOT NULL,
  next_check_at TEXT,
  reason TEXT NOT NULL,
  source_ids TEXT NOT NULL,
  PRIMARY KEY (tracking_key, run_id)
);
CREATE TABLE IF NOT EXISTS thesis_events (
  thesis_key TEXT NOT NULL,
  run_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  event_time TEXT,
  source_sha256 TEXT,
  inclusion TEXT,
  status TEXT,
  PRIMARY KEY (thesis_key, run_id, item_id)
);
"""


def open_db(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _result_field(result: Any, name: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def _packet_digest(packet: dict[str, Any]) -> str:
    encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _thesis_key_from_item(item: dict[str, Any]) -> str:
    explicit = str(item.get("thesis_key") or "").strip()
    if explicit:
        return explicit
    themes = item.get("themes") or ()
    theme = ""
    if isinstance(themes, (list, tuple)) and themes:
        theme = str(themes[0])
    domain = str(item.get("domain") or "unknown")
    return f"{domain}:{theme or 'unknown'}"


def _candidate_rows(packet: dict[str, Any], result: Any) -> list[dict[str, Any]]:
    selected_ids = {getattr(item, "item_id", item.get("item_id") if isinstance(item, dict) else None) for item in (_result_field(result, "selected") or ())}
    rows: list[dict[str, Any]] = []
    packet_items = {str(row.get("item_id") or ""): row for row in (packet.get("items") or []) if isinstance(row, dict)}
    seen: set[str] = set()
    for item in _result_field(result, "selected") or ():
        raw = item if isinstance(item, dict) else {
            "item_id": item.item_id,
            "domain": item.domain,
            "title": item.title,
            "thesis_key": getattr(item, "thesis_key", ""),
            "source_id": getattr(item, "source_id", ""),
            "event_time": item.event_time,
            "publication_time": getattr(item, "publication_time", ""),
            "observation_period": getattr(item, "observation_period", ""),
            "impact_score": item.impact_score,
            "fact": item.fact,
            "source_url": item.source_url,
            "themes": getattr(item, "themes", ()),
        }
        item_id = str(raw.get("item_id") or "")
        raw = {**packet_items.get(item_id, {}), **raw}
        rows.append({
            **raw,
            "item_id": item_id,
            "inclusion": "selected",
            "reasons": [],
            "thesis_key": _thesis_key_from_item(raw),
        })
        seen.add(item_id)
    rejected = _result_field(result, "rejected") or ()
    packet_items = {str(row.get("item_id") or ""): row for row in (packet.get("items") or []) if isinstance(row, dict)}
    for row in rejected:
        item_id = str(row.get("item_id") or "")
        raw = dict(packet_items.get(item_id) or {})
        raw.update({"item_id": item_id, "reasons": list(row.get("reasons") or [])})
        rows.append({
            **raw,
            "inclusion": "excluded",
            "thesis_key": _thesis_key_from_item(raw),
        })
        seen.add(item_id)
    for raw in packet.get("items") or []:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("item_id") or "")
        if item_id in seen:
            continue
        inclusion = "selected" if item_id in selected_ids else "excluded"
        rows.append({
            **raw,
            "inclusion": inclusion,
            "reasons": ["run_blocked"] if _result_field(result, "status") != "pass" else ["not_selected"],
            "thesis_key": _thesis_key_from_item(raw),
        })
    # Duplicate IDs must not create duplicate primary-key writes on blocked input.
    return list({row["item_id"]: row for row in rows}.values())


def ingest_run(
    conn: sqlite3.Connection,
    packet: dict[str, Any],
    result: Any,
    run_dir: Path | None = None,
    *,
    schema_status: str = SCHEMA_STATUS_VERIFIED,
) -> dict[str, Any]:
    run_id = str(packet.get("run_id") or _result_field(result, "as_of") or "").strip()
    if not run_id:
        raise ValueError("run_id or as_of is required to ingest")
    as_of = str(_result_field(result, "as_of") or packet.get("as_of") or "")
    status = str(_result_field(result, "status") or "")
    outcome = str(_result_field(result, "outcome") or "")
    ingested_at = _now()
    if status != "pass" and schema_status == SCHEMA_STATUS_VERIFIED:
        schema_status = "blocked"
    with conn:
        conn.execute(
            """
            INSERT INTO runs (run_id, as_of, status, outcome, run_dir, packet_sha256, schema_status, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
              as_of=excluded.as_of,
              status=excluded.status,
              outcome=excluded.outcome,
              run_dir=excluded.run_dir,
              packet_sha256=excluded.packet_sha256,
              schema_status=excluded.schema_status,
              ingested_at=excluded.ingested_at
            """,
            (
                run_id,
                as_of,
                status,
                outcome,
                str(Path(run_dir).resolve()) if run_dir is not None else packet.get("run_dir"),
                _packet_digest(packet),
                schema_status,
                ingested_at,
            ),
        )
        conn.execute("DELETE FROM sources WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM locators WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM candidates WHERE run_id=?", (run_id,))
        conn.execute("DELETE FROM thesis_events WHERE run_id=?", (run_id,))
        for src in packet.get("sources") or []:
            if not isinstance(src, dict):
                continue
            source_id = str(src.get("source_id") or "").strip()
            if not source_id:
                continue
            kind = str(src.get("kind") or "evidence")
            conn.execute(
                """
                INSERT INTO sources (
                  source_id, run_id, url, requested_url, captured_title, kind,
                  access_completeness, identity_status, sha256, body_path,
                  captured_at, accessed_at, publication_time, publication_time_precision,
                  event_time, event_time_precision, observation_period, recovered_source_id, quote
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    run_id,
                    src.get("url"),
                    src.get("requested_url") or src.get("url"),
                    src.get("captured_title"),
                    kind,
                    src.get("access_completeness"),
                    src.get("identity_status"),
                    src.get("sha256"),
                    src.get("body_path"),
                    src.get("captured_at"),
                    src.get("accessed_at"),
                    src.get("publication_time"),
                    src.get("publication_time_precision"),
                    src.get("event_time"),
                    src.get("event_time_precision"),
                    src.get("observation_period"),
                    src.get("recovered_source_id"),
                    src.get("quote"),
                ),
            )
            if kind == "locator":
                conn.execute(
                    """
                    INSERT INTO locators (locator_id, run_id, url, discovered_at, note)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        run_id,
                        src.get("url"),
                        src.get("captured_at") or src.get("accessed_at"),
                        "locator metadata; not evidence",
                    ),
                )
        source_hash = {
            str(src.get("source_id")): src.get("sha256")
            for src in (packet.get("sources") or [])
            if isinstance(src, dict)
        }
        for row in _candidate_rows(packet, result):
            item_id = str(row.get("item_id") or "")
            thesis_key = str(row.get("thesis_key") or _thesis_key_from_item(row))
            conn.execute(
                """
                INSERT INTO candidates (
                  item_id, run_id, domain, title, thesis_key, inclusion, reasons,
                  source_id, event_time, publication_time, observation_period, impact_score, fact, judgment_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    run_id,
                    row.get("domain"),
                    row.get("title"),
                    thesis_key,
                    row.get("inclusion"),
                    json.dumps(row.get("reasons") or [], ensure_ascii=False),
                    row.get("source_id"),
                    row.get("event_time"),
                    row.get("publication_time"),
                    row.get("observation_period"),
                    row.get("impact_score"),
                    row.get("fact"),
                    json.dumps(row, ensure_ascii=False, default=str),
                ),
            )
            conn.execute(
                """
                INSERT INTO thesis_events (
                  thesis_key, run_id, item_id, event_time, source_sha256, inclusion, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thesis_key,
                    run_id,
                    item_id,
                    row.get("event_time"),
                    source_hash.get(str(row.get("source_id") or "")),
                    row.get("inclusion"),
                    schema_status,
                ),
            )
            if row.get("inclusion") == "selected" and status == "pass":
                previous = conn.execute("SELECT r.as_of FROM thesis_state t JOIN runs r ON t.last_run_id=r.run_id WHERE t.thesis_key=?", (thesis_key,)).fetchone()
                if previous and datetime.fromisoformat(previous["as_of"]) > datetime.fromisoformat(as_of):
                    continue
                conn.execute(
                    """
                    INSERT INTO thesis_state (
                      thesis_key, last_run_id, last_event_time, last_item_id, last_title,
                      last_source_url, last_fact, last_outcome, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(thesis_key) DO UPDATE SET
                      last_run_id=excluded.last_run_id,
                      last_event_time=excluded.last_event_time,
                      last_item_id=excluded.last_item_id,
                      last_title=excluded.last_title,
                      last_source_url=excluded.last_source_url,
                      last_fact=excluded.last_fact,
                      last_outcome=excluded.last_outcome,
                      status=excluded.status,
                      updated_at=excluded.updated_at
                    """,
                    (
                        thesis_key,
                        run_id,
                        row.get("event_time"),
                        item_id,
                        row.get("title"),
                        row.get("source_url"),
                        row.get("fact"),
                        "selected",
                        schema_status,
                        ingested_at,
                    ),
                )
        updates = packet.get("followup_updates") or []
        if not isinstance(updates, list):
            raise ValueError("followup_updates must be a list")
        if updates and status != "pass":
            raise ValueError("blocked run cannot update followups")
        # In the same transaction: malformed review rolls back candidate/run writes too.
        known = {row["tracking_key"] for row in readback_followups(conn, include_closed=True)}
        verified_ids = {
            str(src.get("source_id")) for src in packet.get("sources", [])
            if src.get("kind") == "evidence" and src.get("identity_status") == "match"
            and src.get("access_completeness") in {"full", "excerpt"}
        }
        seen_updates = set()
        # Final-text-only replay must preserve already recorded reviews.
        for update in updates:
            key = str(update.get("tracking_key") or "")
            if key not in known:
                raise ValueError(f"unknown tracking_key: {key}")
            if key in seen_updates:
                raise ValueError(f"duplicate followup update: {key}")
            seen_updates.add(key)
            review_status = update.get("status")
            if review_status not in {"open", "closed", "superseded"}:
                raise ValueError("invalid followup status")
            reason = str(update.get("reason") or "").strip()
            source_ids = update.get("source_ids") or []
            if not reason or not isinstance(source_ids, list) or not source_ids or not set(source_ids) <= verified_ids:
                raise ValueError("followup review requires reason and current verified source_ids")
            next_check = update.get("next_check_at")
            if review_status == "open":
                if not next_check:
                    raise ValueError("open followup review requires next_check_at")
                from .upstream_radar import _parse_aware
                if _parse_aware(next_check, "next_check_at") <= _parse_aware(as_of, "as_of"):
                    raise ValueError("next_check_at must be after run as_of")
            conn.execute(
                "INSERT OR REPLACE INTO followup_reviews VALUES (?, ?, ?, ?, ?, ?)",
                (key, run_id, review_status, next_check, reason, json.dumps(source_ids)),
            )
    return {"run_id": run_id, "status": status, "outcome": outcome, "schema_status": schema_status}


def seed_legacy_from_run(conn: sqlite3.Connection, run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    receipt = json.loads((run_dir / "output" / "run-receipt.json").read_text(encoding="utf-8"))
    selected = json.loads((run_dir / "output" / "selected-items.json").read_text(encoding="utf-8"))
    run_id = f"legacy:{receipt.get('as_of')}"
    packet = {
        "run_id": run_id,
        "as_of": receipt.get("as_of"),
        "sources": [],
        "items": selected if isinstance(selected, list) else [],
    }
    fake_result = {
        "as_of": receipt.get("as_of"),
        "status": receipt.get("status") or "pass",
        "outcome": receipt.get("outcome") or "push",
        "selected": selected if isinstance(selected, list) else [],
        "rejected": [],
    }
    return ingest_run(conn, packet, fake_result, run_dir, schema_status=SCHEMA_STATUS_LEGACY)


def readback_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    run = _as_dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
    if run is None:
        raise KeyError(f"run not found: {run_id}")
    sources = [_as_dict(row) for row in conn.execute("SELECT * FROM sources WHERE run_id=?", (run_id,))]
    locators = [_as_dict(row) for row in conn.execute("SELECT * FROM locators WHERE run_id=?", (run_id,))]
    candidates = []
    for row in conn.execute("SELECT * FROM candidates WHERE run_id=?", (run_id,)):
        item = _as_dict(row)
        assert item is not None
        try:
            item["reasons"] = json.loads(item["reasons"] or "[]")
        except json.JSONDecodeError:
            item["reasons"] = []
        item["judgment"] = json.loads(item.pop("judgment_json") or "{}")
        candidates.append(item)
    run.update({
        "sources": sources,
        "locators": locators,
        "candidates": candidates,
        "followup_updates": [dict(row) for row in conn.execute("SELECT * FROM followup_reviews WHERE run_id=?", (run_id,))],
        "candidate_count": len(candidates),
        "source_count": len(sources),
    })
    return run


def readback_thesis_state(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT t.*, c.judgment_json, r.run_dir FROM thesis_state t LEFT JOIN candidates c ON c.run_id=t.last_run_id AND c.item_id=t.last_item_id LEFT JOIN runs r ON r.run_id=t.last_run_id ORDER BY t.updated_at, t.thesis_key").fetchall()
    result = []
    for row in rows:
        item = _as_dict(row) or {}
        item["judgment"] = json.loads(item.pop("judgment_json") or "{}")
        result.append(item)
    return result


def latest_success_as_of(conn: sqlite3.Connection, *, exclude_run_id: str = "") -> datetime | None:
    rows = conn.execute("SELECT as_of FROM runs WHERE status='pass' AND run_id != ?", (exclude_run_id,))
    values = [datetime.fromisoformat(row["as_of"]) for row in rows]
    return max(values) if values else None


def trusted_catchup_boundary(conn: sqlite3.Connection, packet: dict, objective) -> datetime | None:
    from .upstream_radar import _parse_aware
    previous = latest_success_as_of(conn, exclude_run_id=str(packet.get("run_id") or ""))
    as_of = _parse_aware(packet.get("as_of"), "as_of")
    if previous and (packet.get("catchup_since") or (as_of - previous).total_seconds() > objective.max_age_hours * 3600):
        return previous
    return None


def validate_continuity(conn: sqlite3.Connection, packet: dict, result, objective) -> list[str]:
    """Gate the ordinary writer before a pass can advance the research watermark.

    Returns required due follow-ups left unreviewed. They stay due (never silently
    advanced) and are reported; they block only a silent/no-push run, because a
    publishable issue should not be held hostage by one unresolved question.
    """
    if _result_field(result, "status") != "pass" or not objective.require_opportunity_context:
        return []
    from .upstream_radar import _parse_aware
    boundary = trusted_catchup_boundary(conn, packet, objective)
    if boundary is not None and (not packet.get("catchup_since") or _parse_aware(packet["catchup_since"], "catchup_since") != boundary):
        raise ValueError("missing or mismatched required catchup_since")
    as_of = _parse_aware(packet.get("as_of"), "as_of")
    latest = latest_success_as_of(conn)
    if latest is not None and latest > as_of:
        return []  # historical replay never owns current due-state completion
    due = {row['tracking_key'] for row in readback_followups(conn, as_of) if row['due'] and row['required']}
    selected_ids = {item.item_id for item in _result_field(result, 'selected', ())}
    covered = {
        str(row.get('tracking_key') or row.get('item_id'))
        for row in packet.get('items', []) if row.get('item_id') in selected_ids
    }
    covered.update(str(row.get('tracking_key')) for row in packet.get('followup_updates', []))
    # Reviews saved earlier in this same run are valid on final-artifact replay.
    covered.update(row['tracking_key'] for row in conn.execute(
        'SELECT tracking_key FROM followup_reviews WHERE run_id=?', (str(packet.get('run_id') or ''),)))
    missing = due - covered
    if missing and _result_field(result, "outcome") != "push":
        raise ValueError("due followups not reviewed: " + ", ".join(sorted(missing)))
    return sorted(missing)


def readback_followups(
    conn: sqlite3.Connection, now: datetime | None = None, *, include_closed: bool = False,
) -> list[dict[str, Any]]:
    """Latest state per entity/question, never latest item per broad theme.

    Old selected candidates are implicitly open without rewriting legacy evidence.
    Explicit stable tracking_key links later evidence; no key means the exact item_id.
    This is current operational state, not an as-of historical reconstruction API.
    """
    now = now or datetime.now(TZ)
    candidates = conn.execute(
        "SELECT c.*, r.as_of, r.schema_status, r.run_dir FROM candidates c "
        "JOIN runs r ON r.run_id=c.run_id WHERE c.inclusion='selected' AND r.status='pass'"
    ).fetchall()
    state: dict[str, dict[str, Any]] = {}
    for candidate in sorted(candidates, key=lambda r: (datetime.fromisoformat(r['as_of']), r['run_id'], r['item_id'])):
        item = dict(candidate)
        judgment = json.loads(item.pop("judgment_json") or "{}")
        key = str(judgment.get("tracking_key") or item["item_id"])
        state[key] = {
            "tracking_key": key, "item_id": item["item_id"], "run_id": item["run_id"],
            "thesis_key": item["thesis_key"], "title": item["title"],
            "schema_status": item["schema_status"], "run_dir": item["run_dir"],
            "as_of": item["as_of"], "status": "open", "next_check_at": None,
            "judgment": judgment,
        }
    reviews = conn.execute(
        "SELECT f.*, r.as_of FROM followup_reviews f JOIN runs r ON r.run_id=f.run_id WHERE r.status='pass'"
    ).fetchall()
    for review in sorted(reviews, key=lambda r: (datetime.fromisoformat(r['as_of']), r['run_id'])):
        item = state.get(review['tracking_key'])
        if item is not None and datetime.fromisoformat(review['as_of']) >= datetime.fromisoformat(item['as_of']):
            item.update(status=review['status'], next_check_at=review['next_check_at'],
                        last_review_at=review['as_of'], review_reason=review['reason'],
                        review_run_id=review['run_id'])
    result = []
    for item in state.values():
        # Questions expire instead of accumulating forever. After
        # FOLLOWUP_STALE_DAYS without new selected evidence a question stops being
        # required; it gets one optional day at its scheduled check, then expires
        # unless a review gave it a later named node. FOLLOWUP_MAX_DAYS is a hard cap.
        age = now - datetime.fromisoformat(item['as_of'])
        next_check = datetime.fromisoformat(item['next_check_at']) if item['next_check_at'] else None
        if item['status'] == 'open' and (
            age > timedelta(days=FOLLOWUP_MAX_DAYS)
            or (age > timedelta(days=FOLLOWUP_STALE_DAYS)
                and (next_check is None or next_check <= now - timedelta(days=1)))
        ):
            item['status'] = 'expired'
        if not include_closed and item['status'] != 'open':
            continue
        item['due'] = item['status'] == 'open' and (next_check is None or next_check <= now)
        item['required'] = item['due'] and age <= timedelta(days=FOLLOWUP_STALE_DAYS)
        result.append(item)
    return sorted(result, key=lambda item: (not item['due'], item['next_check_at'] or item['as_of'], item['tracking_key']))


def readback_all(conn: sqlite3.Connection) -> dict[str, Any]:
    runs = [_as_dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY as_of")]
    return {
        "runs": runs,
        "thesis_state": readback_thesis_state(conn),
        "open_followups": readback_followups(conn),
        "hash_verifies_bytes_not_truth": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest and read back the upstream radar SQLite index.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ingest_p = sub.add_parser("ingest")
    ingest_p.add_argument("--db", type=Path, required=True)
    ingest_p.add_argument("--packet", type=Path, required=True)
    ingest_p.add_argument("--receipt", type=Path, required=True)
    ingest_p.add_argument("--run-dir", type=Path)
    ingest_p.add_argument("--config", type=Path)
    ingest_p.add_argument("--schema-status", default=SCHEMA_STATUS_VERIFIED)
    read_p = sub.add_parser("readback")
    read_p.add_argument("--db", type=Path, required=True)
    read_p.add_argument("--run-id")
    read_p.add_argument("--thesis", action="store_true")
    seed_p = sub.add_parser("seed-legacy")
    seed_p.add_argument("--db", type=Path, required=True)
    seed_p.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    conn = open_db(args.db)
    if args.cmd == "ingest":
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        # Re-evaluate the packet and captured files; a caller-written PASS is not evidence.
        from .upstream_radar import DEFAULT_CONFIG, evaluate_packet, load_objective
        run_dir = args.run_dir or args.packet.parent
        objective = load_objective(args.config or DEFAULT_CONFIG)
        evaluation = evaluate_packet(packet, objective, run_dir=run_dir, catchup_since=trusted_catchup_boundary(conn, packet, objective))
        validate_continuity(conn, packet, evaluation, objective)
        result = ingest_run(conn, packet, evaluation, run_dir, schema_status="verified" if evaluation.status == "pass" else "blocked")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.cmd == "seed-legacy":
        result = seed_legacy_from_run(conn, args.run_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.run_id:
        print(json.dumps(readback_run(conn, args.run_id), ensure_ascii=False, indent=2))
    elif args.thesis:
        print(json.dumps(readback_thesis_state(conn), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(readback_all(conn), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
