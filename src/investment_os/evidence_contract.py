from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

EVIDENCE_STATUSES = frozenset(
    {
        "source_target_only",
        "primary_metadata_only",
        "primary_body_retrieved",
        "primary_body_read",
        "single_source_data",
        "cross_checked_data",
        "mixed_sources",
        "stale",
        "unavailable",
    }
)

_STATUS_ALIASES = {
    "primary_read": "primary_body_read",
    "primary_data": "single_source_data",
    "secondary_cross_check": "cross_checked_data",
    "config_only": "source_target_only",
    "demo_fixture": "single_source_data",
    "unknown": "unavailable",
    "": "",
}


@dataclass(frozen=True)
class SourceError:
    code: str
    message: str
    source_url: str = ""
    transient: bool = False
    occurred_at: str = ""

    def to_dict(self) -> dict[str, str | bool]:
        return asdict(self)


def normalize_evidence_status(row: Mapping[str, object]) -> str:
    raw_explicit = str(row.get("evidence_status", "") or "").strip()
    explicit = raw_explicit
    explicit = _STATUS_ALIASES.get(explicit, explicit)
    source_type = str(row.get("source_type", "") or "").strip()
    confidence = str(row.get("confidence", "") or "").strip().lower()
    source = str(row.get("source", "") or "").strip()
    source_url = str(row.get("source_url", "") or "").strip()
    as_of_date = str(row.get("as_of_date", "") or "").strip()
    content_hash = str(row.get("content_hash", "") or "").strip()
    body_read_status = str(row.get("body_read_status", "") or "").strip().lower()
    freshness_status = str(row.get("freshness_status", "") or "").strip().lower()

    if explicit == "stale" or freshness_status == "stale":
        return "stale"
    if explicit == "unavailable":
        return "unavailable"
    if explicit in {
        "source_target_only",
        "primary_metadata_only",
        "primary_body_retrieved",
        "mixed_sources",
    }:
        return explicit

    market_source = source_type in {
        "market_proxy_prices_live",
        "market_data",
        "china_market_data_single_source",
    }
    if market_source:
        if confidence in {"market_data_mixed", "mixed_sources", "mixed"}:
            return "mixed_sources"
        if confidence == "market_data_cross_checked":
            return "cross_checked_data"
        return "single_source_data" if source and as_of_date else "unavailable"

    # A retrieval event cannot self-upgrade into a read event. Callers must use
    # a read-specific source type after they have actually inspected relevant sections.
    if source_type == "primary_filing_body_retrieved":
        if source_url and content_hash:
            return "primary_body_retrieved"
        return "primary_metadata_only"

    filing_body = source_type == "primary_filing_body_read"
    if filing_body:
        if body_read_status == "retrieved" and source_url and content_hash:
            return "primary_body_retrieved"
        if body_read_status == "read" and source_url and content_hash:
            return "primary_body_read"
        if (raw_explicit == "primary_read" or body_read_status == "legacy_read") and source_url:
            return "primary_body_read"
        return "primary_metadata_only"
    if explicit == "primary_body_read" or raw_explicit == "primary_read":
        return "primary_metadata_only"

    if source_type in {"primary_sec_recent_filing", "primary_sec_identity"}:
        return "primary_metadata_only"
    if source_type in {"primary_macro_calendar", "primary_macro_rates", "watchlist_config"}:
        return "source_target_only"
    if source_type.startswith("primary_") and source_url and as_of_date:
        return "single_source_data"
    if source and source_type and as_of_date:
        return "single_source_data"
    return "unavailable"


def infer_body_read_status(source_type: str, content_hash: str, current: str = "") -> str:
    if source_type == "primary_filing_body_retrieved":
        return "retrieved" if content_hash else "metadata_only"
    if current:
        return current
    if source_type == "primary_filing_body_read" and content_hash:
        return "read"
    if source_type in {"primary_sec_recent_filing", "primary_sec_identity"}:
        return "metadata_only"
    return "not_read"
