from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

COVERAGE_OK = {"checked", "checked_no_change"}
USABLE_COMPLETENESS = {"full", "excerpt"}
FULL_READ_STATUS = {"primary_read", "verified_data"}
IDENTITY_MATCH = "match"
NO_PUSH_LINE = "截至今早，本轮已核验来源中未发现需要新增推送的变化。"
# A deployment may set these before use; the packet rules below do not depend on them.
DEFAULT_CONFIG = Path("configs/upstream_radar.sample.yaml")
DEFAULT_READER_ID = "reader"
BRIEF_TITLE_STATUS = "# 上游投资信号"
BRIEF_TITLE_ITEMS = "# 投资机会与关键变化"
TRADE_TERMS = (
    "买入",
    "卖出",
    "持有",
    "加仓",
    "减仓",
    "清仓",
    "满仓",
    "仓位",
    "目标价",
    "下单",
    "buy",
    "sell",
    "hold",
    "overweight",
    "underweight",
    "position sizing",
    "position size",
    "execute",
    "execution",
    "trade",
    "trading",
)


@dataclass(frozen=True)
class UpstreamRadarObjective:
    reader_id: str
    objective: str
    decision_horizon: str
    max_age_hours: int
    minimum_source_authority: int
    minimum_impact_score: int
    allowed_evidence_status: tuple[str, ...]
    required_checks: dict[str, tuple[str, ...]]
    topic_keywords: dict[str, tuple[str, ...]]
    decision_dimensions: tuple[str, ...]
    allowed_action_types: tuple[str, ...]
    advisory_boundary: str
    require_opportunity_context: bool = False
    silent_no_push: bool = False
    research_sources: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpstreamRadarItem:
    item_id: str
    domain: str
    title: str
    event_time: str
    source_url: str
    source_authority: int
    evidence_status: str
    themes: tuple[str, ...]
    fact: str
    transmission: str
    affected_dimensions: tuple[str, ...]
    impact_score: int
    changed_since_last_run: bool
    action_type: str
    next_research_action: str
    falsifier: str
    age_hours: float
    source_id: str = ""
    thesis_key: str = ""
    prior_view: str = ""
    evidence_delta: str = ""
    interpretation: str = ""
    counterevidence: str = ""
    declared_gaps: str = ""
    observation_period: str = ""
    publication_time: str = ""
    bounded_quote: str = ""
    opportunity_hypothesis: str = ""
    affected_companies: str = ""
    expectation_gap: str = ""
    valuation_context: str = ""
    discovery_status: str = "new"


@dataclass(frozen=True)
class UpstreamRadarResult:
    status: str
    outcome: str
    as_of: str
    selected: tuple[UpstreamRadarItem, ...]
    rejected: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]
    coverage: tuple[dict[str, Any], ...]
    gaps: tuple[str, ...] = ()


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def load_objective(path: Path) -> UpstreamRadarObjective:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    required_checks = {
        str(domain): _tuple_strings(checks)
        for domain, checks in (raw.get("required_checks") or {}).items()
    }
    topic_keywords = {
        str(domain): _tuple_strings(keywords)
        for domain, keywords in (raw.get("topic_keywords") or {}).items()
    }
    return UpstreamRadarObjective(
        reader_id=str(raw.get("reader_id", DEFAULT_READER_ID)),
        objective=str(raw.get("objective", "")),
        decision_horizon=str(raw.get("decision_horizon", "")),
        max_age_hours=int(raw.get("max_age_hours", 72)),
        minimum_source_authority=int(raw.get("minimum_source_authority", 4)),
        minimum_impact_score=int(raw.get("minimum_impact_score", 4)),
        allowed_evidence_status=_tuple_strings(raw.get("allowed_evidence_status")),
        required_checks=required_checks,
        topic_keywords=topic_keywords,
        decision_dimensions=_tuple_strings(raw.get("decision_dimensions")),
        allowed_action_types=_tuple_strings(raw.get("allowed_action_types")),
        advisory_boundary=str(raw.get("advisory_boundary", "")),
        require_opportunity_context=raw.get("require_opportunity_context") is True,
        silent_no_push=raw.get("silent_no_push") is True,
        research_sources=dict(raw.get("research_sources") or {}),
    )


def _parse_aware(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _has_trade_instruction(text: str) -> bool:
    lower = text.lower()
    for term in TRADE_TERMS:
        if term.isascii():
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(term)}(?![A-Za-z0-9_-])", lower):
                return True
        elif term in text:
            return True
    return False


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_run_file(run_dir: Path, relative: str) -> Path:
    rel = str(relative or "").strip()
    if not rel:
        raise ValueError("path escape: empty body_path")
    path = Path(rel)
    if path.is_absolute():
        raise ValueError(f"path escape: absolute body_path {rel}")
    if ".." in path.parts:
        raise ValueError(f"path escape: {rel}")
    root = run_dir.resolve()
    cursor = Path(run_dir)
    for part in path.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError(f"symlink escape: {rel}")
    resolved = (run_dir / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escape: {rel}") from exc
    if resolved.exists() and resolved.is_symlink():
        raise ValueError(f"symlink escape: {rel}")
    return resolved


def _index_sources(raw: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if raw in (None, []):
        return {}, []
    if not isinstance(raw, list):
        return {}, ["sources must be a list"]
    indexed: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            errors.append("source must be an object")
            continue
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            errors.append("source missing source_id")
            continue
        if source_id in indexed:
            errors.append(f"duplicate source_id: {source_id}")
            continue
        indexed[source_id] = row
    return indexed, errors


def _load_source_body(src: dict[str, Any], run_dir: Path | None) -> tuple[str | None, str | None]:
    source_id = str(src.get("source_id") or "<missing>")
    body_path = str(src.get("body_path") or "").strip()
    completeness = str(src.get("access_completeness") or "")
    if completeness == "blocked" and not body_path:
        return None, None
    if src.get("kind") == "locator" and not body_path:
        return None, None
    if not body_path:
        if completeness in USABLE_COMPLETENESS:
            return None, f"source {source_id} missing body_path"
        return None, None
    if run_dir is None:
        return None, f"source {source_id} needs run_dir to resolve body_path"
    try:
        path = resolve_run_file(run_dir, body_path)
    except ValueError as exc:
        return None, f"source {source_id} {exc}"
    if not path.is_file():
        return None, f"source {source_id} body_path not a file"
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    declared = str(src.get("sha256") or "").strip().lower()
    if not declared:
        return None, f"source {source_id} missing sha256"
    if digest != declared:
        return None, f"source {source_id} sha256 mismatch"
    try:
        text = data.decode("utf-8")
        if not text.strip():
            return None, f"source {source_id} empty body"
        return text, None
    except UnicodeDecodeError:
        return None, f"source {source_id} requires a readable UTF-8 text capture"


def _source_ids_for_row(row: dict[str, Any]) -> list[str]:
    ids = row.get("source_ids")
    if isinstance(ids, list) and ids:
        return list(dict.fromkeys(str(item).strip() for item in ids if str(item).strip()))
    return []


def _enrich_coverage_row(
    row: dict[str, Any],
    sources_by_id: dict[str, dict[str, Any]],
    bodies: dict[str, str],
    source_errors: dict[str, str],
) -> dict[str, Any]:
    source_ids = _source_ids_for_row(row)
    verified: list[str] = []
    invalid: list[str] = []
    locators: list[str] = []
    partial: list[str] = []
    blocked: list[str] = []
    missing: list[str] = []
    for source_id in source_ids:
        src = sources_by_id.get(source_id)
        if src is None:
            missing.append(source_id)
            continue
        kind = str(src.get("kind") or "evidence")
        completeness = str(src.get("access_completeness") or "")
        identity = str(src.get("identity_status") or "")
        if kind == "locator":
            locators.append(source_id)
            continue
        if identity == "mismatch" or completeness == "blocked":
            invalid.append(source_id)
            blocked.append(source_id)
            continue
        if completeness == "partial":
            partial.append(source_id)
            continue
        if identity != IDENTITY_MATCH:
            invalid.append(source_id)
            continue
        if completeness not in USABLE_COMPLETENESS:
            invalid.append(source_id)
            continue
        if source_id in source_errors or source_id not in bodies:
            invalid.append(source_id)
            continue
        verified.append(source_id)
    enriched = dict(row)
    enriched["verified_source_ids"] = verified
    enriched["invalid_source_ids"] = invalid
    enriched["locator_source_ids"] = locators
    enriched["partial_source_ids"] = partial
    enriched["missing_source_ids"] = missing
    enriched["derived_source_count"] = len(verified)
    enriched["hash_verifies_bytes_not_truth"] = True
    return enriched


def _coverage_errors(
    coverage: list[dict[str, Any]],
    objective: UpstreamRadarObjective,
    sources_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in coverage:
        key = (str(row.get("domain", "")), str(row.get("check", "")))
        indexed.setdefault(key, []).append(row)

    for domain, checks in objective.required_checks.items():
        for check in checks:
            rows = indexed.get((domain, check), [])
            if not rows:
                errors.append(f"coverage missing: {domain}/{check}")
                continue
            if len(rows) != 1:
                errors.append(f"coverage duplicated: {domain}/{check}")
                continue
            row = rows[0]
            status = str(row.get("status", ""))
            source_ids = _source_ids_for_row(row)
            declared_count = row.get("source_count")
            if not source_ids:
                if int(declared_count or 0) > 0 or row.get("sources"):
                    errors.append(f"coverage counts-only without receipts: {domain}/{check}")
                else:
                    errors.append(f"coverage has no verified evidence: {domain}/{check}")
            derived = int(row.get("derived_source_count") or 0)
            if status not in COVERAGE_OK:
                errors.append(f"coverage not usable: {domain}/{check} status={status or 'missing'}")
            if derived < 1:
                if row.get("partial_source_ids"):
                    errors.append(f"coverage partial cannot count as full-read: {domain}/{check}")
                elif source_ids:
                    errors.append(f"coverage has no verified evidence: {domain}/{check}")
            if declared_count not in (None, "") and source_ids and int(declared_count) != derived:
                errors.append(f"coverage source_count mismatch: {domain}/{check}")
            for source_id in source_ids:
                if source_id not in sources_by_id:
                    errors.append(f"coverage missing source_id {source_id}: {domain}/{check}")
    return errors


def _age_anchor(raw: dict[str, Any], event_time: datetime) -> datetime:
    publication = str(raw.get("publication_time") or "").strip()
    if publication:
        try:
            return _parse_aware(publication, "publication_time")
        except ValueError:
            return event_time
    return event_time


def _item_from_raw(
    raw: dict[str, Any],
    objective: UpstreamRadarObjective,
    as_of: datetime,
    sources_by_id: dict[str, dict[str, Any]],
    bodies: dict[str, str],
    catchup_since: datetime | None = None,
) -> tuple[UpstreamRadarItem | None, list[str], list[str]]:
    reasons: list[str] = []
    blocking: list[str] = []
    item_id = str(raw.get("item_id", "")).strip() or "<missing>"
    domain = str(raw.get("domain", "")).strip()
    if domain not in objective.required_checks:
        reasons.append("outside_objective_domain")

    required_text = (
        "title",
        "event_time",
        "source_url",
        "evidence_status",
        "fact",
        "transmission",
        "action_type",
        "next_research_action",
        "falsifier",
        "prior_view",
        "evidence_delta",
        "interpretation",
    )
    if objective.require_opportunity_context:
        required_text += ("opportunity_hypothesis", "affected_companies", "expectation_gap", "valuation_context")
    for name in required_text:
        if not str(raw.get(name, "")).strip():
            reasons.append(f"missing_{name}")
    if not str(raw.get("counterevidence") or "").strip() and not str(raw.get("declared_gaps") or "").strip():
        reasons.append("missing_counterevidence_or_declared_gaps")

    try:
        event_time = _parse_aware(raw.get("event_time", ""), "event_time")
    except ValueError:
        reasons.append("invalid_event_time")
        event_time = as_of
    age_source = sources_by_id.get(str(raw.get("source_id") or "")) or {}
    age_ref = min(_age_anchor(raw, event_time), _age_anchor(age_source, event_time)) if age_source.get("publication_time") else _age_anchor(raw, event_time)
    age_hours = (as_of - age_ref).total_seconds() / 3600
    if age_hours < 0:
        reasons.append("future_event_time")
        blocking.append(f"future evidence: {item_id}")
    elif age_hours > objective.max_age_hours:
        if not (catchup_since is not None and age_ref >= catchup_since and raw.get("discovery_status") == "catchup"):
            reasons.append("stale_event")

    source_url = str(raw.get("source_url", "")).strip()
    if source_url and not _valid_url(source_url):
        reasons.append("invalid_source_url")

    source_id = str(raw.get("source_id") or "").strip()
    if not source_id:
        reasons.append("missing_source_id")
        src = None
    else:
        src = sources_by_id.get(source_id)
        if src is None:
            reasons.append("unknown_source_id")
        else:
            if source_url != str(src.get("url") or ""):
                reasons.append("source_url_mismatch")
            if source_id not in bodies:
                reasons.append("source_body_unavailable")
            completeness = str(src.get("access_completeness") or "")
            identity = str(src.get("identity_status") or "")
            kind = str(src.get("kind") or "evidence")
            if kind == "locator":
                reasons.append("locator_is_not_evidence")
            if identity == "mismatch":
                reasons.append("source_identity_mismatch")
            elif identity != IDENTITY_MATCH:
                reasons.append("source_identity_unverified")
            if completeness not in USABLE_COMPLETENESS:
                reasons.append("source_completeness_unusable")
            if completeness == "partial":
                reasons.append("partial_not_full_read")
            elif completeness == "blocked":
                reasons.append("blocked_source")
            evidence_status = str(raw.get("evidence_status", "")).strip()
            if evidence_status in FULL_READ_STATUS and completeness != "full":
                reasons.append("not_full_read")
            if completeness == "excerpt":
                quote = str(raw.get("bounded_quote") or "").strip()
                body = bodies.get(source_id) or ""
                if not quote:
                    reasons.append("excerpt_missing_bounded_quote")
                elif quote not in body:
                    reasons.append("excerpt_quote_not_in_body")

    source_authority = int(raw.get("source_authority") or 0)
    if source_authority < objective.minimum_source_authority:
        reasons.append("weak_source_authority")
    evidence_status = str(raw.get("evidence_status", "")).strip()
    if evidence_status not in objective.allowed_evidence_status:
        reasons.append("unsupported_evidence_status")

    themes = _tuple_strings(raw.get("themes"))
    allowed_topics = {value.lower() for value in objective.topic_keywords.get(domain, ())}
    if domain in objective.required_checks and not allowed_topics.intersection(value.lower() for value in themes):
        reasons.append("not_upstream_theme")

    affected_dimensions = _tuple_strings(raw.get("affected_dimensions"))
    allowed_dimensions = set(objective.decision_dimensions)
    if not allowed_dimensions.intersection(affected_dimensions):
        reasons.append("no_decision_dimension")

    impact_score = int(raw.get("impact_score") or 0)
    if impact_score < objective.minimum_impact_score:
        reasons.append("low_decision_impact")
    if raw.get("changed_since_last_run") is not True:
        reasons.append("not_a_new_change")

    action_type = str(raw.get("action_type", "")).strip()
    if action_type not in objective.allowed_action_types:
        reasons.append("unsupported_research_action")
    protected_text = " ".join(
        str(raw.get(field, ""))
        for field in ("title", "fact", "transmission", "next_research_action", "falsifier", "prior_view", "evidence_delta", "interpretation", "counterevidence", "declared_gaps", "opportunity_hypothesis", "affected_companies", "expectation_gap", "valuation_context")
    )
    if _has_trade_instruction(protected_text):
        reasons.append("trade_instruction")
        blocking.append(f"advisory boundary violated: {item_id}")

    if reasons:
        return None, reasons, blocking
    thesis_key = str(raw.get("thesis_key") or "").strip()
    if not thesis_key:
        thesis_key = f"{domain}:{themes[0] if themes else 'unknown'}"
    publication_time = str(raw.get("publication_time") or "").strip()
    return (
        UpstreamRadarItem(
            item_id=item_id,
            domain=domain,
            title=str(raw["title"]).strip(),
            event_time=event_time.isoformat(),
            source_url=source_url,
            source_authority=source_authority,
            evidence_status=evidence_status,
            themes=themes,
            fact=str(raw["fact"]).strip(),
            transmission=str(raw["transmission"]).strip(),
            affected_dimensions=affected_dimensions,
            impact_score=impact_score,
            changed_since_last_run=True,
            action_type=action_type,
            next_research_action=str(raw["next_research_action"]).strip(),
            falsifier=str(raw["falsifier"]).strip(),
            age_hours=round(age_hours, 2),
            source_id=source_id,
            thesis_key=thesis_key,
            prior_view=str(raw.get("prior_view") or "").strip(),
            evidence_delta=str(raw.get("evidence_delta") or "").strip(),
            interpretation=str(raw.get("interpretation") or "").strip(),
            counterevidence=str(raw.get("counterevidence") or "").strip(),
            declared_gaps=str(raw.get("declared_gaps") or "").strip(),
            observation_period=str(raw.get("observation_period") or "").strip(),
            publication_time=publication_time,
            bounded_quote=str(raw.get("bounded_quote") or "").strip(),
            opportunity_hypothesis=str(raw.get("opportunity_hypothesis") or "").strip(),
            affected_companies=str(raw.get("affected_companies") or "").strip(),
            expectation_gap=str(raw.get("expectation_gap") or "").strip(),
            valuation_context=str(raw.get("valuation_context") or "").strip(),
            discovery_status=str(raw.get("discovery_status") or "new"),
        ),
        [],
        [],
    )


def evaluate_packet(
    packet: dict[str, Any],
    objective: UpstreamRadarObjective,
    *,
    run_dir: Path | None = None,
    catchup_since: datetime | None = None,
) -> UpstreamRadarResult:
    errors: list[str] = []
    try:
        as_of = _parse_aware(packet.get("as_of", ""), "as_of")
    except ValueError as exc:
        errors.append(str(exc))
        as_of = datetime.now().astimezone()

    if catchup_since is not None and (catchup_since.tzinfo is None or catchup_since > as_of):
        errors.append("invalid trusted catchup_since")
        catchup_since = None
    if catchup_since is not None and not packet.get("catchup_since"):
        errors.append("missing required catchup_since for uncovered interval")
    if packet.get("catchup_since"):
        try:
            if catchup_since is None or _parse_aware(packet["catchup_since"], "catchup_since") != catchup_since:
                errors.append("catchup_since does not match trusted database boundary")
        except ValueError as exc:
            errors.append(str(exc))

    if run_dir is None and packet.get("run_dir"):
        run_dir = Path(str(packet["run_dir"]))

    sources_by_id, source_index_errors = _index_sources(packet.get("sources"))
    errors.extend(source_index_errors)
    bodies: dict[str, str] = {}
    source_errors: dict[str, str] = {}
    # A bad source disqualifies itself (and items/coverage built on it),
    # not the whole issue. Gaps only block when nothing qualified is left to publish.
    run_errors = errors
    errors = []
    for source_id, src in sources_by_id.items():
        if not _valid_url(str(src.get("url") or "")):
            errors.append(f"source {source_id} invalid URL")
        if src.get("kind") == "evidence" and src.get("access_completeness") in USABLE_COMPLETENESS:
            for field in ("captured_at", "accessed_at"):
                try:
                    timestamp = _parse_aware(src.get(field), field)
                    if timestamp > as_of:
                        errors.append(f"source {source_id} future {field}")
                    elif (as_of - timestamp).total_seconds() > 86400:
                        errors.append(f"source {source_id} stale capture {field}")
                except ValueError:
                    errors.append(f"source {source_id} missing/invalid {field}")
            for field in ("publication_time", "event_time"):
                if src.get(field):
                    try:
                        timestamp = _parse_aware(src[field], field)
                        if timestamp > as_of:
                            errors.append(f"source {source_id} future {field}")
                    except ValueError:
                        errors.append(f"source {source_id} invalid {field}")
                    if not src.get(field + "_precision"):
                        errors.append(f"source {source_id} missing {field}_precision")
        body, error = _load_source_body(src, run_dir)
        if error:
            errors.append(error)
        if body is not None:
            bodies[source_id] = body
        source_problems = [e for e in errors if e.startswith(f"source {source_id} ")]
        if source_problems:
            source_errors[source_id] = source_problems[0]
            bodies.pop(source_id, None)
    gaps: list[str] = list(errors)
    errors = run_errors

    coverage_raw = packet.get("coverage") or []
    coverage = coverage_raw if isinstance(coverage_raw, list) else []
    if not isinstance(coverage_raw, list):
        errors.append("coverage must be a list")
        coverage = []
    enriched = [_enrich_coverage_row(row, sources_by_id, bodies, source_errors) if isinstance(row, dict) else {"invalid": True} for row in coverage]
    gaps.extend(_coverage_errors([row for row in enriched if "domain" in row], objective, sources_by_id))

    items_raw = packet.get("items") or []
    if not isinstance(items_raw, list):
        errors.append("items must be a list")
        items_raw = []

    qualified: list[UpstreamRadarItem] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in items_raw:
        if not isinstance(raw, dict):
            rejected.append({"item_id": "<invalid>", "reasons": ["item_must_be_object"]})
            continue
        item_id = str(raw.get("item_id", "")).strip() or "<missing>"
        if item_id in seen_ids:
            rejected.append({"item_id": item_id, "reasons": ["duplicate_item_id"]})
            continue
        seen_ids.add(item_id)
        item, reasons, blocking = _item_from_raw(raw, objective, as_of, sources_by_id, bodies, catchup_since)
        errors.extend(blocking)
        if item is None:
            rejected.append({"item_id": item_id, "reasons": reasons})
        else:
            qualified.append(item)

    selected = sorted(
        qualified,
        key=lambda item: (item.impact_score, item.source_authority, -item.age_hours, item.item_id),
        reverse=True,
    )
    artifact = packet.get("delivery_artifact")
    # Omitted final permits research selection before drafting. An explicitly
    # supplied final must be usable for push; an empty one is not acceptance.
    if selected and "delivery_artifact" in packet:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("text"), str) or not artifact["text"].strip():
            errors.append("missing/empty final text: delivery_artifact")
    if "writing_gate" in packet:
        gate = packet["writing_gate"]
        if not isinstance(gate, dict) or gate.get("status") != "pass" or gate.get("delivery_authorized") is not True:
            errors.append("writing_gate has not authorized final delivery")
    if isinstance(artifact, dict):
        final_text = str(artifact.get("text") or "")
        if _has_trade_instruction(final_text):
            errors.append("advisory boundary violated: delivery_artifact")
        if selected and "[SILENT]" in final_text:
            errors.append("push delivery cannot contain silent suppression marker")
    if gaps and not selected:
        # Silence would claim "checked, nothing new" over unchecked ground.
        errors.extend(gaps)
    status = "fail" if errors else "pass"
    if status == "fail":
        outcome = "blocked"
        selected = []
    else:
        outcome = "push" if selected else "no_push"
    return UpstreamRadarResult(
        status=status,
        outcome=outcome,
        as_of=as_of.isoformat(),
        selected=tuple(selected),
        rejected=tuple(rejected),
        errors=tuple(errors),
        coverage=tuple(dict(row) for row in enriched),
        gaps=tuple(gaps) if status == "pass" else (),
    )


def _downgrade_sentence(text: str) -> str:
    clean = text.rstrip("。.")
    if clean.startswith(("若", "如果")):
        return f"{clean}。" if "应下调" in clean else f"{clean}，当前判断应下调。"
    prefix = "若 " if clean[:1].isascii() and clean[:1].isalpha() else "若"
    if clean.endswith("应下调"):
        return f"{prefix}{clean}。"
    return f"{prefix}{clean}，当前判断应下调。"


def render_reader_brief(
    result: UpstreamRadarResult,
    objective: UpstreamRadarObjective,
) -> str:
    local_date = _parse_aware(result.as_of, "as_of").date().isoformat()
    if result.status != "pass":
        return f"{BRIEF_TITLE_STATUS}\n\n本轮来源覆盖或研究边界没有通过，停止生成读者推送。\n"
    if not result.selected:
        if objective.silent_no_push:
            return ""
        return (
            f"{BRIEF_TITLE_STATUS}\n\n"
            f"{NO_PUSH_LINE}\n\n"
            "只用于个人投资研究与风险判断，不是交易建议。\n"
        )

    lines = [BRIEF_TITLE_ITEMS, ""]
    for item in result.selected:
        counter = item.counterevidence or item.declared_gaps or "未声明反证或缺口。"
        lines.extend(
            [
                f"## {'补发现｜' if item.discovery_status == 'catchup' else ''}{item.title.rstrip('。.')}",
                "",
                f"{item.prior_view.rstrip('。.')}。{item.evidence_delta.rstrip('。.')}。",
                f"{item.interpretation.rstrip('。.')}。{counter.rstrip('。.')}。",
                "",
                *([f"{item.opportunity_hypothesis} {item.affected_companies}", f"{item.expectation_gap} {item.valuation_context}", ""] if objective.require_opportunity_context else []),
                f"接下来核验：{item.next_research_action.rstrip('。.')}。{_downgrade_sentence(item.falsifier)}",
                "",
                f"[来源]({item.source_url})",
                "",
            ]
        )
    lines.append(f"资料截至：{local_date}。只用于个人投资研究与风险判断，不是交易建议。")
    lines.append("")
    return "\n".join(lines)


def _atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".pending")
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def write_outputs(
    result: UpstreamRadarResult,
    objective: UpstreamRadarObjective,
    out_dir: Path,
    *,
    packet: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    brief_path = out_dir / "reader-brief.md"
    selected_path = out_dir / "selected-items.json"
    receipt_path = out_dir / "run-receipt.json"
    delivery_path = out_dir / "delivery-final.md"
    # Invalidate earlier success before any fallible DB/state work.
    _atomic_text(receipt_path, json.dumps({"status": "pending", "as_of": result.as_of}))
    _atomic_text(delivery_path, "本轮研究尚未完成，不能据此判断有无机会。")
    _atomic_text(brief_path, "本轮研究尚未完成。")
    _atomic_text(selected_path, "[]")
    unreviewed_due: list[str] = []
    if db_path is not None and packet is not None:
        from .radar_store import ingest_run, open_db, validate_continuity
        try:
            conn = open_db(db_path)
            try:
                unreviewed_due = validate_continuity(conn, packet, result, objective)
                ingest_run(conn, packet, result, run_dir)
            finally:
                conn.close()
        except Exception as exc:
            _atomic_text(receipt_path, json.dumps({"status": "fail", "outcome": "blocked", "as_of": result.as_of, "errors": [str(exc)], "claim_sent": False}, ensure_ascii=False))
            _atomic_text(delivery_path, "本轮投资研究状态校验失败，不能据此判断有无新机会。\n" + str(exc))
            raise
    brief_path.write_text(render_reader_brief(result, objective), encoding="utf-8")
    selected_path.write_text(
        json.dumps([asdict(item) for item in result.selected], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifact = (packet or {}).get("delivery_artifact") if packet else None
    stored = False
    if result.outcome == "no_push" and objective.silent_no_push:
        delivery_path.write_text("[SILENT]", encoding="utf-8")
        stored = True
    elif result.status != "pass":
        delivery_path.write_text("本轮投资研究存在来源或校验缺口，不能据此判断有无新机会。\n" + "\n".join(result.errors), encoding="utf-8")
        stored = True
    elif isinstance(artifact, dict) and str(artifact.get("text") or ""):
        delivery_path.write_text(str(artifact.get("text")), encoding="utf-8")
        stored = True
    elif delivery_path.exists():
        delivery_path.write_text("", encoding="utf-8")  # stale previous final is not this run

    receipt = {
        "status": result.status,
        "outcome": result.outcome,
        "as_of": result.as_of,
        "objective": objective.objective,
        "selected_items": len(result.selected),
        "rejected_items": len(result.rejected),
        "rejected": list(result.rejected),
        "errors": list(result.errors),
        "gaps": list(result.gaps),
        "unreviewed_due_followups": unreviewed_due,
        "coverage": list(result.coverage),
        "advisory_boundary": objective.advisory_boundary,
        "item_cap": "none",
        "hash_verifies_bytes_not_truth": True,
        "delivery_artifact_stored": stored,
        "claim_sent": False,
        "renderer_is_not_delivery_proof": True,
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = {"brief": brief_path, "selected": selected_path, "receipt": receipt_path}
    if stored:
        paths["delivery_final"] = delivery_path
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an agent-written evidence packet, select qualifying items and store the run.")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--delivery-file", type=Path,
                        help="Attach the reviewed UTF-8 final verbatim; no inline Python required.")
    args = parser.parse_args(argv)

    objective = load_objective(args.config)
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    if args.delivery_file is not None:
        text = args.delivery_file.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("empty delivery file")
        packet["delivery_artifact"] = dict(kind="agent_final", text=text, claim_sent=False)
        pending = args.packet.with_name(args.packet.name + ".delivery.tmp")
        pending.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pending.replace(args.packet)
    run_dir = args.run_dir or args.packet.parent
    catchup_since = None
    if args.db is not None:
        if not args.db.is_file():
            raise ValueError("runtime requires established radar database")
        from .radar_store import open_db, trusted_catchup_boundary
        with open_db(args.db) as conn:
            catchup_since = trusted_catchup_boundary(conn, packet, objective)
    result = evaluate_packet(packet, objective, run_dir=run_dir, catchup_since=catchup_since)
    write_outputs(result, objective, args.out, packet=packet, run_dir=run_dir, db_path=args.db)
    print(json.dumps({"status": result.status, "outcome": result.outcome, "selected_items": len(result.selected), "output": str(args.out), "claim_sent": False}, ensure_ascii=False))
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
