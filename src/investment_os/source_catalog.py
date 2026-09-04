from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


SOURCE_ID_RE = re.compile(r"[a-z0-9-]+")
ALLOWED_SOURCE_KINDS = {"expert", "media"}
ALLOWED_ROUTING_TIERS = {
    "shared_core_on_demand",
    "theme_counterview_on_demand",
    "explicit_need_only",
}
ALLOWED_VIEWPOINT_ROLES = {"discovery", "mechanism", "consensus", "context", "counterview"}
ALLOWED_ACCESS_STATES = {
    "public",
    "public_transport_variable",
    "public_and_subscriber_mix",
    "mixed_paywall",
    "account_required",
    "paid_product",
    "not_available",
}
ALLOWED_CAPTURE_MODES = {
    "web_extract",
    "web_search_then_web_extract",
    "x_search_if_available_else_web_search",
    "youtube_metadata_then_public_transcript",
    "web_search_guest_interview_then_public_transcript",
    "not_configured_do_not_claim",
}
CHANNEL_TYPE_ORDER = {
    "rss": 0,
    "website": 1,
    "x": 2,
    "podcast": 3,
    "youtube": 4,
    "paid_feed": 5,
}
TIER_SCORE = {
    "shared_core_on_demand": 3,
    "theme_counterview_on_demand": 1,
    "explicit_need_only": 0,
}


class SourceCatalogError(ValueError):
    """Raised when the catalog or a source request cannot be used safely."""


def _non_empty_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise SourceCatalogError(f"{label} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise SourceCatalogError(f"{label} must contain non-empty strings")
    return value


def validate_source_catalog(catalog: object) -> dict[str, Any]:
    if not isinstance(catalog, dict):
        raise SourceCatalogError("source catalog root must be an object")
    failures: list[str] = []
    if catalog.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    if catalog.get("catalog_id") != "investment-os-public-source-catalog":
        failures.append("catalog_id is invalid")
    if catalog.get("dispatch_mode") != "on_demand_only":
        failures.append("dispatch_mode must be on_demand_only")
    policy = catalog.get("policy")
    if not isinstance(policy, dict) or not all(
        isinstance(policy.get(field), str) and policy[field].strip()
        for field in ("selection", "authority", "access", "video", "deduplication")
    ):
        failures.append("policy is incomplete")

    sources = catalog.get("sources")
    if not isinstance(sources, list) or not sources:
        failures.append("sources must be a non-empty list")
        sources = []
    expected_count = catalog.get("expected_source_count")
    if expected_count != len(sources):
        failures.append("expected_source_count does not match sources")
    expected_kind_counts = catalog.get("expected_kind_counts")
    if not isinstance(expected_kind_counts, dict):
        failures.append("expected_kind_counts must be an object")
        expected_kind_counts = {}
    seen_ids: set[str] = set()
    kind_counts = {kind: 0 for kind in ALLOWED_SOURCE_KINDS}
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            failures.append(f"{label} must be an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or SOURCE_ID_RE.fullmatch(source_id) is None:
            failures.append(f"{label}.id must be a lowercase slug")
        elif source_id in seen_ids:
            failures.append(f"duplicate source id: {source_id}")
        else:
            seen_ids.add(source_id)
            label = source_id
        if source.get("kind") not in ALLOWED_SOURCE_KINDS:
            failures.append(f"{label}.kind is invalid")
        else:
            kind_counts[source["kind"]] += 1
        for field in ("name", "organization"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                failures.append(f"{label}.{field} must be non-empty")
        if source.get("source_role") != "discovery_not_fact_authority":
            failures.append(f"{label}.source_role must preserve discovery-only authority")
        if source.get("routing_tier") not in ALLOWED_ROUTING_TIERS:
            failures.append(f"{label}.routing_tier is invalid")
        for field in ("topics", "geographies", "viewpoint_roles", "use_limits"):
            value = source.get(field)
            if not isinstance(value, list) or not value or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                failures.append(f"{label}.{field} must be a non-empty string list")
        roles = source.get("viewpoint_roles", [])
        if isinstance(roles, list) and any(role not in ALLOWED_VIEWPOINT_ROLES for role in roles):
            failures.append(f"{label}.viewpoint_roles contains an invalid role")

        channels = source.get("channels")
        if not isinstance(channels, list) or not channels:
            failures.append(f"{label}.channels must be a non-empty list")
            continue
        channel_keys: set[tuple[str, str]] = set()
        for channel_index, channel in enumerate(channels):
            channel_label = f"{label}.channels[{channel_index}]"
            if not isinstance(channel, dict):
                failures.append(f"{channel_label} must be an object")
                continue
            channel_type = channel.get("type")
            if channel_type not in CHANNEL_TYPE_ORDER:
                failures.append(f"{channel_label}.type is invalid")
            if not isinstance(channel.get("priority"), int) or not 1 <= channel["priority"] <= 4:
                failures.append(f"{channel_label}.priority must be 1..4")
            for field in ("status", "access_state", "capture"):
                if not isinstance(channel.get(field), str) or not channel[field].strip():
                    failures.append(f"{channel_label}.{field} must be non-empty")
            status = channel.get("status")
            if isinstance(status, str) and re.fullmatch(r"[a-z0-9_]+", status) is None:
                failures.append(f"{channel_label}.status must be a lowercase state")
            access_state = channel.get("access_state")
            if access_state not in ALLOWED_ACCESS_STATES:
                failures.append(f"{channel_label}.access_state is invalid")
            capture = channel.get("capture")
            if capture not in ALLOWED_CAPTURE_MODES:
                failures.append(f"{channel_label}.capture is invalid")
            if (
                capture != "not_configured_do_not_claim"
                and access_state != "not_available"
                and isinstance(status, str)
                and not status.startswith("verified_")
            ):
                failures.append(f"{channel_label}.active channel status must be verified")
            url = channel.get("url")
            query = channel.get("query")
            if url is not None:
                parsed = urlparse(url) if isinstance(url, str) else None
                if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    failures.append(f"{channel_label}.url must be absolute http(s)")
            if not url and not query:
                failures.append(f"{channel_label} needs a url or query")
            identity = str(url or query or channel.get("handle") or "")
            key = (str(channel_type), identity.casefold())
            if key in channel_keys:
                failures.append(f"{channel_label} duplicates another channel")
            channel_keys.add(key)
            if channel_type == "x" and capture == "x_search_if_available_else_web_search":
                handle = channel.get("handle")
                if not isinstance(handle, str) or re.fullmatch(r"@[A-Za-z0-9_]{1,15}", handle) is None:
                    failures.append(f"{channel_label}.handle is invalid")
                elif isinstance(url, str) and url.rstrip("/").rsplit("/", 1)[-1].casefold() != handle[1:].casefold():
                    failures.append(f"{channel_label}.url does not match handle")
            if channel_type == "youtube" and isinstance(status, str) and status.startswith("verified_"):
                channel_id = channel.get("channel_id")
                if not isinstance(channel_id, str) or re.fullmatch(r"UC[A-Za-z0-9_-]{20,}", channel_id) is None:
                    failures.append(f"{channel_label}.channel_id is required for verified YouTube")
                if not isinstance(url, str):
                    failures.append(f"{channel_label}.url is required for verified YouTube")
            if capture == "web_search_guest_interview_then_public_transcript":
                if not isinstance(query, str) or not query.strip():
                    failures.append(f"{channel_label}.query is required for guest interviews")
                if channel.get("speaker_verification_required") is not True:
                    failures.append(f"{channel_label} must require speaker verification")
    for kind, count in kind_counts.items():
        if expected_kind_counts.get(kind) != count:
            failures.append(f"expected {kind} count does not match sources")
    if failures:
        raise SourceCatalogError("invalid source catalog:\n- " + "\n- ".join(failures))
    return catalog


def load_source_catalog(path: Path) -> dict[str, Any]:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceCatalogError(f"source catalog is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceCatalogError(f"source catalog is not valid JSON: {path}: {exc}") from exc
    return validate_source_catalog(catalog)


def load_source_request(path: Path) -> dict[str, Any]:
    try:
        request = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceCatalogError(f"source request is missing: {path}") from exc
    except yaml.YAMLError as exc:
        raise SourceCatalogError(f"source request is not valid YAML: {path}: {exc}") from exc
    if not isinstance(request, dict):
        raise SourceCatalogError("source request root must be an object")
    return request


def _validate_request(catalog: dict[str, Any], request: object) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise SourceCatalogError("source request root must be an object")
    if request.get("schema_version") != 1:
        raise SourceCatalogError("source request schema_version must be 1")
    decision = request.get("decision")
    access = request.get("access")
    limits = request.get("limits")
    if not isinstance(decision, dict) or not isinstance(access, dict) or not isinstance(limits, dict):
        raise SourceCatalogError("source request requires decision, access, and limits objects")

    topics = _non_empty_strings(decision.get("topics"), "decision.topics")
    geographies = _non_empty_strings(decision.get("geographies"), "decision.geographies")
    roles = _non_empty_strings(decision.get("viewpoint_roles"), "decision.viewpoint_roles")
    if any(role not in ALLOWED_VIEWPOINT_ROLES for role in roles):
        raise SourceCatalogError("decision.viewpoint_roles contains an invalid role")
    if not isinstance(decision.get("time_window"), str) or not decision["time_window"].strip():
        raise SourceCatalogError("decision.time_window must be non-empty")

    source_kinds = _non_empty_strings(access.get("source_kinds"), "access.source_kinds")
    if any(kind not in ALLOWED_SOURCE_KINDS for kind in source_kinds):
        raise SourceCatalogError("access.source_kinds contains an invalid kind")
    candidate_source_ids = _non_empty_strings(
        access.get("candidate_source_ids"), "access.candidate_source_ids"
    )
    allowed_access_states = _non_empty_strings(
        access.get("allowed_access_states"), "access.allowed_access_states"
    )
    known_access_states = {
        channel["access_state"]
        for source in catalog["sources"]
        for channel in source["channels"]
    }
    if any(state not in known_access_states for state in allowed_access_states):
        raise SourceCatalogError("access.allowed_access_states contains an unknown state")
    if not isinstance(access.get("allow_explicit_need_only"), bool):
        raise SourceCatalogError("access.allow_explicit_need_only must be explicit true or false")

    include_ids = access.get("include_source_ids")
    exclude_ids = access.get("exclude_source_ids")
    if not isinstance(include_ids, list) or any(not isinstance(item, str) for item in include_ids):
        raise SourceCatalogError("access.include_source_ids must be a string list")
    if not isinstance(exclude_ids, list) or any(not isinstance(item, str) for item in exclude_ids):
        raise SourceCatalogError("access.exclude_source_ids must be a string list")
    known_ids = {source["id"] for source in catalog["sources"]}
    unknown_ids = sorted((set(candidate_source_ids) | set(include_ids) | set(exclude_ids)) - known_ids)
    if unknown_ids:
        raise SourceCatalogError("source request references unknown source ids: " + ", ".join(unknown_ids))
    if not set(include_ids) <= set(candidate_source_ids):
        raise SourceCatalogError("access.include_source_ids must stay inside candidate_source_ids")
    if set(include_ids) & set(exclude_ids):
        raise SourceCatalogError("a source cannot be both included and excluded")

    max_sources = limits.get("max_sources")
    max_channels = limits.get("max_channels_per_source")
    if not isinstance(max_sources, int) or not 1 <= max_sources <= len(catalog["sources"]):
        raise SourceCatalogError("limits.max_sources is out of range")
    if not isinstance(max_channels, int) or not 1 <= max_channels <= 4:
        raise SourceCatalogError("limits.max_channels_per_source must be 1..4")

    known_topics = {topic for source in catalog["sources"] for topic in source["topics"]}
    if not set(topics) & known_topics and not include_ids:
        raise SourceCatalogError("decision.topics does not match the catalog and no source was explicitly included")
    known_geographies = {geo for source in catalog["sources"] for geo in source["geographies"]}
    if not set(geographies) & known_geographies and "global" not in geographies:
        raise SourceCatalogError("decision.geographies does not match the catalog")
    return request


def _matching_geographies(source_geographies: set[str], requested: set[str]) -> list[str]:
    direct = sorted(source_geographies & requested)
    if direct:
        return direct
    if "global" in source_geographies:
        return ["global"]
    return []


def _available_channels(source: dict[str, Any], allowed_access: set[str], limit: int) -> list[dict[str, Any]]:
    channels = [
        channel
        for channel in source["channels"]
        if channel["access_state"] in allowed_access
        and channel["capture"] != "not_configured_do_not_claim"
        and channel["access_state"] != "not_available"
        and channel["status"].startswith("verified_")
    ]
    channels.sort(key=lambda item: (item["priority"], CHANNEL_TYPE_ORDER[item["type"]], item.get("url", "")))
    return channels[:limit]


def resolve_source_plan(catalog: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    catalog = validate_source_catalog(catalog)
    request = _validate_request(catalog, request)
    decision = request["decision"]
    access = request["access"]
    limits = request["limits"]
    topics = set(decision["topics"])
    geographies = set(decision["geographies"])
    roles = set(decision["viewpoint_roles"])
    source_kinds = set(access["source_kinds"])
    allowed_access = set(access["allowed_access_states"])
    candidate_source_ids = set(access["candidate_source_ids"])
    include_ids = set(access["include_source_ids"])
    exclude_ids = set(access["exclude_source_ids"])
    allow_explicit = access["allow_explicit_need_only"]

    candidates: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    for source in catalog["sources"]:
        source_id = source["id"]
        explicit_include = source_id in include_ids
        if source_id not in candidate_source_ids:
            exclusions.append({"source_id": source_id, "reason": "outside_reader_source_pool"})
            continue
        if source_id in exclude_ids:
            exclusions.append({"source_id": source_id, "reason": "reader_excluded"})
            continue
        if source["kind"] not in source_kinds:
            exclusions.append({"source_id": source_id, "reason": "source_kind_not_requested"})
            continue
        if source["routing_tier"] == "explicit_need_only" and not (allow_explicit and explicit_include):
            exclusions.append({"source_id": source_id, "reason": "explicit_need_permission_required"})
            continue

        matched_topics = sorted(topics & set(source["topics"]))
        matched_roles = sorted(roles & set(source["viewpoint_roles"]))
        matched_geographies = _matching_geographies(set(source["geographies"]), geographies)
        if not explicit_include and not matched_topics:
            exclusions.append({"source_id": source_id, "reason": "no_topic_match"})
            continue
        if not explicit_include and not matched_roles:
            exclusions.append({"source_id": source_id, "reason": "no_viewpoint_role_match"})
            continue
        if not explicit_include and not matched_geographies:
            exclusions.append({"source_id": source_id, "reason": "no_geography_match"})
            continue

        channels = _available_channels(source, allowed_access, limits["max_channels_per_source"])
        if not channels:
            exclusions.append({"source_id": source_id, "reason": "no_permitted_active_channel"})
            continue
        score = (
            (1000 if explicit_include else 0)
            + 20 * len(matched_topics)
            + 7 * len(matched_roles)
            + 5 * len(matched_geographies)
            + TIER_SCORE[source["routing_tier"]]
        )
        candidates.append(
            {
                "source_id": source_id,
                "name": source["name"],
                "organization": source["organization"],
                "kind": source["kind"],
                "routing_tier": source["routing_tier"],
                "selection_reason": "explicit_include" if explicit_include else "reader_need_match",
                "matched_topics": matched_topics,
                "matched_geographies": matched_geographies,
                "matched_viewpoint_roles": matched_roles,
                "use_limits": source["use_limits"],
                "source_role": source["source_role"],
                "score": score,
                "channels": channels,
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["source_id"]))
    selected = candidates[: limits["max_sources"]]
    for candidate in candidates[limits["max_sources"] :]:
        exclusions.append({"source_id": candidate["source_id"], "reason": "below_max_sources_cutoff"})
    exclusions.sort(key=lambda item: item["source_id"])
    return {
        "schema_version": 1,
        "catalog_id": catalog["catalog_id"],
        "catalog_as_of": catalog["as_of"],
        "dispatch_mode": catalog["dispatch_mode"],
        "decision": decision,
        "access": access,
        "limits": limits,
        "fact_authority_required": True,
        "selected_sources": selected,
        "excluded_sources": exclusions,
    }


def build_source_plan(catalog_path: Path, request_path: Path, out_path: Path) -> dict[str, Any]:
    catalog = load_source_catalog(catalog_path)
    request = load_source_request(request_path)
    plan = resolve_source_plan(catalog, request)
    plan["catalog_sha256"] = "sha256:" + hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    plan["request_sha256"] = "sha256:" + hashlib.sha256(request_path.read_bytes()).hexdigest()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(out_path.name + ".tmp")
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, out_path)
    return plan
