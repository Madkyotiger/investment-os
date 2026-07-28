from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping, Sequence

from .evidence_contract import normalize_evidence_status


MEANINGFUL_IMPACTS = {"strengthened", "weakened", "unknown_narrowed", "unknown_expanded"}
METADATA_SOURCE_TYPES = {"primary_sec_recent_filing", "primary_sec_identity"}
BACKGROUND_SOURCE_TYPES = {"primary_macro_calendar", "primary_macro_rates", "watchlist_config"}
EVIDENCE_STATUS_RANK = {
    "primary_body_read": 6,
    "cross_checked_data": 4,
    "single_source_data": 3,
    "primary_metadata_only": 2,
    "source_target_only": 1,
    "mixed_sources": 1,
    "stale": 0,
    "unavailable": 0,
}


@dataclass(frozen=True)
class ChangeAssessment:
    change_type: str
    meaningful_change: bool
    reason: str
    evidence_fingerprint: str


def _text(row: Mapping[str, object], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def infer_topic_key(row: Mapping[str, object]) -> str:
    explicit = _text(row, "thesis_key")
    if explicit:
        return explicit

    item_id = _text(row, "item_id")
    source_type = _text(row, "source_type")
    tickers = _text(row, "tickers")
    lane = _text(row, "lane")

    if source_type == "primary_macro_fred_live":
        return f"macro:{item_id.rsplit(':', 1)[-1].lower()}"
    if source_type in {"primary_macro_fred_yields_live", "primary_macro_rates"} or "yield_curve" in item_id:
        return "macro:rates-duration"
    if source_type == "primary_macro_calendar" or "fed_calendar" in item_id:
        return "macro:fed-calendar"
    if source_type == "market_proxy_prices_live":
        return "market:cross-asset-move"
    if source_type == "primary_sec_recent_filing" or item_id.startswith("primary_sec:") and "latest_filing" in item_id:
        return f"company:{tickers or item_id.split(':')[1]}:filing"
    if source_type == "primary_sec_identity":
        return f"company:{tickers or item_id.split(':')[1]}:sec-identity"
    if source_type == "watchlist_config":
        return f"watchlist:{tickers or item_id}"
    if tickers.startswith("theme:"):
        return tickers
    if "sector_theme_discovery:theme:" in item_id:
        return item_id.split("sector_theme_discovery:", 1)[1]
    if lane == "company_events" and tickers:
        return f"company:{tickers}:fundamentals"
    if lane == "market_action" and tickers:
        return f"market:{tickers}"
    return item_id or _text(row, "title") or "unknown"


def infer_geography(row: Mapping[str, object]) -> str:
    explicit = _text(row, "geography")
    if explicit:
        return explicit
    text = " ".join([_text(row, "tickers"), _text(row, "title"), _text(row, "themes")])
    tokens = re.split(r"[,/\s]+", text.upper())
    if any(re.fullmatch(r"\d{6}", token) or token.endswith((".SZ", ".SS", ".SH")) for token in tokens):
        return "China"
    if "CHINA" in text.upper() or "CSI" in text.upper() or "A-SHARE" in text.upper():
        return "China"
    if "theme:" in text.lower() or _text(row, "lane") == "sector_theme_discovery":
        return "Global"
    return "US"


def infer_evidence_status(row: Mapping[str, object]) -> str:
    return normalize_evidence_status(row)


def infer_research_question(row: Mapping[str, object]) -> str:
    explicit = _text(row, "research_question")
    if explicit:
        return explicit
    source_type = _text(row, "source_type")
    ticker = _text(row, "tickers") or "该公司"
    if source_type == "primary_sec_recent_filing":
        return f"{ticker} 这份披露正文是否包含会改变经营、风险或资本配置判断的新事实？"
    if source_type in {"primary_macro_fred_live", "primary_macro_fred_yields_live", "primary_macro_rates"}:
        return "利率变化是否得到美元、期限资产与成长板块相对表现的交叉确认？"
    if source_type in {"market_proxy_prices_live", "market_data"}:
        return "这次价格变化来自公司事实、行业 beta，还是资金与情绪？"
    next_check = _text(row, "next_check")
    if next_check:
        return next_check.rstrip("。.") + "？"
    return "这条信息改变了哪一个既有研究假设？"


def infer_counter_explanation(row: Mapping[str, object]) -> str:
    explicit = _text(row, "counter_explanation")
    if explicit:
        return explicit
    source_type = _text(row, "source_type")
    cannot_prove = _text(row, "cannot_prove")
    if source_type == "primary_sec_recent_filing":
        return "它可能只是例行披露；元数据本身没有经营含义。"
    if source_type in {"market_proxy_prices_live", "market_data"}:
        return cannot_prove or "价格变化可能只是 beta 或流动性，不能单独证明原因。"
    return cannot_prove or _text(row, "kill_signal") or "现有资料还不足以排除其他解释。"


def infer_next_primary_source(row: Mapping[str, object]) -> str:
    explicit = _text(row, "next_primary_source")
    if explicit:
        return explicit
    source_type = _text(row, "source_type")
    if source_type == "primary_sec_recent_filing":
        return "披露正文、最新电话会记录与相关业务附注。"
    return _text(row, "next_check") or "下一份相关公司披露或监管原文。"


def enrich_candidate_row(row: Mapping[str, object]) -> dict[str, object]:
    enriched = dict(row)
    enriched["thesis_key"] = infer_topic_key(row)
    enriched["research_question"] = infer_research_question(row)
    enriched["thesis_impact"] = _text(row, "thesis_impact") or "unknown"
    enriched["counter_explanation"] = infer_counter_explanation(row)
    enriched["next_primary_source"] = infer_next_primary_source(row)
    enriched["evidence_status"] = infer_evidence_status(row)
    enriched["geography"] = infer_geography(row)
    return enriched


def is_promotable(row: Mapping[str, object]) -> bool:
    enriched = enrich_candidate_row(row)
    evidence_status = _text(enriched, "evidence_status")
    if evidence_status in {
        "source_target_only",
        "primary_metadata_only",
        "mixed_sources",
        "stale",
        "unavailable",
    }:
        return False
    required = ("item_id", "lane", "title", "summary", "source", "as_of_date")
    if any(not _text(enriched, field) for field in required):
        return False
    synthetic = "synthetic" in _text(enriched, "source").lower() or _text(enriched, "source_type").startswith("demo_")
    if not _text(enriched, "source_url") and not synthetic:
        return False
    if evidence_status == "primary_body_read":
        return bool(
            _text(enriched, "body_read_status") == "read"
            and _text(enriched, "content_hash")
            and _text(enriched, "source_url")
        ) or _text(enriched, "body_read_status") == "legacy_read"
    return True


def evidence_fingerprint(row: Mapping[str, object]) -> str:
    enriched = enrich_candidate_row(row)
    payload = {
        "source": _text(enriched, "source"),
        "source_type": _text(enriched, "source_type"),
        "source_url": _text(enriched, "source_url"),
        "as_of_date": _text(enriched, "as_of_date"),
        "confidence": _text(enriched, "confidence"),
        "evidence_status": _text(enriched, "evidence_status"),
        "thesis_impact": _text(enriched, "thesis_impact"),
        "evidence_digest": _text(enriched, "evidence_digest"),
        "content_hash": _text(enriched, "content_hash"),
        "observed_value": _text(enriched, "observed_value"),
        "freshness_status": _text(enriched, "freshness_status"),
        "freshness_threshold_days": _text(enriched, "freshness_threshold_days"),
        "cannot_prove": _text(enriched, "cannot_prove"),
        "next_primary_source": _text(enriched, "next_primary_source"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def is_fresh(row: Mapping[str, object], generated_at: datetime, max_age_days: int = 3) -> bool:
    freshness_status = _text(row, "freshness_status").lower()
    if freshness_status == "stale":
        return False
    try:
        source_threshold = int(float(_text(row, "freshness_threshold_days")))
    except ValueError:
        source_threshold = max_age_days
    if source_threshold <= 0:
        return False
    source_date = _parse_date(_text(row, "as_of_date"))
    if source_date is None:
        return False
    age = (generated_at.date() - source_date).days
    return 0 <= age <= source_threshold


def classify_change(
    previous: Mapping[str, object] | None,
    row: Mapping[str, object],
    generated_at: datetime,
) -> ChangeAssessment:
    enriched = enrich_candidate_row(row)
    source_type = _text(enriched, "source_type")
    evidence_status = _text(enriched, "evidence_status")
    impact = _text(enriched, "thesis_impact") or "unknown"
    fingerprint = evidence_fingerprint(enriched)

    if source_type in METADATA_SOURCE_TYPES or evidence_status == "primary_metadata_only":
        return ChangeAssessment("metadata_only", False, "只有元数据，尚未读到可解释的正文事实", fingerprint)
    if source_type in BACKGROUND_SOURCE_TYPES or evidence_status in {
        "source_target_only",
        "stale",
        "unavailable",
        "mixed_sources",
    }:
        return ChangeAssessment("background_only", False, "来源目标或配置只构成背景，不构成判断变化", fingerprint)
    if not is_fresh(enriched, generated_at):
        return ChangeAssessment("background_only", False, "资料不在当前变化窗口内，只能作为研究背景", fingerprint)

    if previous is None:
        if impact in MEANINGFUL_IMPACTS:
            return ChangeAssessment("new_question", True, "新的一手证据建立了可证伪研究问题", fingerprint)
        return ChangeAssessment("background_only", False, "尚未说明这条资料改变了哪个既有假设", fingerprint)

    previous_fingerprint = _text(previous, "evidence_fingerprint")
    previous_summary = " ".join(_text(previous, "last_summary").split())
    latest_summary = " ".join(_text(enriched, "summary").split())
    if previous_fingerprint == fingerprint:
        if previous_summary != latest_summary:
            return ChangeAssessment("wording_only", False, "来源与证据没有变化，只是摘要措辞变化", fingerprint)
        return ChangeAssessment("unchanged", False, "证据与判断均未变化", fingerprint)

    change_type = {
        "strengthened": "hypothesis_strengthened",
        "weakened": "hypothesis_weakened",
        "unknown_narrowed": "unknown_narrowed",
        "unknown_expanded": "unknown_expanded",
    }.get(impact)
    if change_type:
        return ChangeAssessment(change_type, True, "新证据明确改变了研究假设或关键未知", fingerprint)
    return ChangeAssessment("evidence_without_impact", False, "证据载体发生变化，但尚未说明判断影响", fingerprint)


def representative_rank(row: Mapping[str, object]) -> tuple[int, int, int, int, str]:
    enriched = enrich_candidate_row(row)

    def number(key: str) -> int:
        try:
            return int(float(str(enriched.get(key, 0) or 0)))
        except ValueError:
            return 0

    return (
        EVIDENCE_STATUS_RANK.get(_text(enriched, "evidence_status"), 0),
        number("source_authority"),
        number("freshness"),
        number("decision_usefulness"),
        _text(enriched, "as_of_date"),
    )


def select_representative_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        enriched = enrich_candidate_row(row)
        grouped.setdefault(_text(enriched, "thesis_key"), []).append(enriched)
    selected = [max(group, key=representative_rank) for group in grouped.values()]
    return sorted(selected, key=lambda row: _text(row, "thesis_key"))
