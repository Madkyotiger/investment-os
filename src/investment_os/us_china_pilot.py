from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol

from .expert_signal_ingest import (
    EXPERT_SIGNAL_CATEGORIES,
    load_expert_signal_seeds,
    render_public_expert_signal_crosswalk,
)
from .pipeline import DISCLAIMER
from .source_verification_crosswalk import (
    EXPERT_SOURCE_VERIFICATION_CATEGORIES,
    load_source_verification_seeds,
    render_source_verification_crosswalk,
)
from .spike1_1_global_us_hardening import (
    DEFAULT_MACRO_PROXIES,
    DEFAULT_SECTOR_PROXY,
    DEFAULT_SECTOR_PROXY_LABELS,
    GlobalUSResearchMemo,
    GlobalUSSymbolConfig,
    build_global_us_memo,
    collect_peer_labels,
    fetch_peer_financial_profiles,
    fetch_proxy_profiles,
    parse_symbol_arg as parse_us_symbol_arg,
)
from .spike1_research_memo import EvidenceItem, write_ledger
from .spike2_china_data import (
    ChinaResearchMemo,
    ChinaSymbolConfig,
    build_china_memo,
    parse_symbol_arg as parse_china_symbol_arg,
)

DEFAULT_US_SYMBOLS = [
    "AAPL:equity:XLK:Apple",
    "MSFT:equity:XLK:Microsoft",
    "NVDA:equity:XLK:NVIDIA",
    "GOOGL:equity:XLC:Alphabet",
    "AMZN:equity:XLY:Amazon",
]

DEFAULT_CHINA_SYMBOLS = [
    "510300:etf:沪深300ETF",
    "000300:index:沪深300指数",
]

FORBIDDEN_REPORT_PHRASES = [
    "建议买入",
    "建议卖出",
    "建议持有",
    "建议加仓",
    "建议减仓",
    "目标收益",
    "自动下单",
    "recommend buy",
    "recommend sell",
    "recommend hold",
]

EXTERNAL_NOTE_FORBIDDEN_PHRASES = FORBIDDEN_REPORT_PHRASES + [
    "买入",
    "卖出",
    "持有",
    "加仓",
    "减仓",
    "清仓",
    "recommendation to buy",
    "recommendation to sell",
    "recommendation to hold",
    "position sizing",
]

EXTERNAL_NOTE_HYPE_PHRASES = [
    "10倍",
    "20倍",
    "10x",
    "20x",
    "韭菜",
    "收割",
    "跟着机构",
    "爆发机会",
    "确定性机会",
    "guaranteed upside",
    "sure thing",
    "follow smart money",
]

EXTERNAL_NOTE_FORBIDDEN_MARKERS = [
    "/mnt/",
    ".cache",
    "uv run",
    "scripts/",
    "reports/us-china-pilot",
    "local DataOS",
    "info_cache=",
    "markdown_cache=",
    "sections_cache=",
]

EXPERT_DISCUSSION_CATEGORIES = EXPERT_SIGNAL_CATEGORIES | EXPERT_SOURCE_VERIFICATION_CATEGORIES

PeerMetricRow = tuple[str, dict[str, str], EvidenceItem]

VALUATION_PE_RATIO_SPREAD_THRESHOLD = 0.25
VALUATION_PB_RATIO_SPREAD_THRESHOLD = 0.35
PROFIT_MARGIN_POINT_SPREAD_THRESHOLD = 10.0
REVENUE_GROWTH_POINT_SPREAD_THRESHOLD = 5.0
DEBT_TO_EQUITY_POINT_SPREAD_THRESHOLD = 20.0
CURRENT_RATIO_POINT_SPREAD_THRESHOLD = 0.5


class MemoLike(Protocol):
    symbol: str
    evidence: list[EvidenceItem]
    evidence_gaps: list[str]

    @property
    def ok_count(self) -> int: ...

    @property
    def issue_count(self) -> int: ...


@dataclass
class LaneSummary:
    lane: str
    symbols: int
    evidence_items: int
    ok_items: int
    review_items_or_gaps: int


@dataclass
class USChinaPilotResult:
    report_path: Path
    ledger_csv_path: Path
    ledger_json_path: Path
    boundary_scan_path: Path
    external_note_path: Path
    external_quality_scan_path: Path


def _collect_evidence(memos: Iterable[MemoLike]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for memo in memos:
        items.extend(memo.evidence)
    return items


def _summarize_lane(lane: str, memos: list[MemoLike]) -> LaneSummary:
    items = _collect_evidence(memos)
    return LaneSummary(
        lane=lane,
        symbols=len(memos),
        evidence_items=len(items),
        ok_items=sum(1 for item in items if item.status == "ok"),
        review_items_or_gaps=sum(1 for item in items if item.status != "ok") + sum(len(memo.evidence_gaps) for memo in memos),
    )


def _all_gaps(lane: str, memos: list[MemoLike]) -> list[str]:
    gaps: list[str] = []
    for memo in memos:
        for gap in memo.evidence_gaps:
            gaps.append(f"{lane}:{memo.symbol}: {gap}")
    return gaps


def _status_counts(items: list[EvidenceItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return dict(sorted(counts.items()))


def _category_counts(items: list[EvidenceItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category] = counts.get(item.category, 0) + 1
    return dict(sorted(counts.items()))


def _parse_semicolon_metrics(value: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for part in value.split(";"):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        metrics[key.strip()] = raw_value.strip()
    return metrics


def _safe_table_cell(value: str, limit: int = 180) -> str:
    cleaned = " ".join(str(value).split()).replace("|", "/")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "…"


def _peer_symbol_from_claim(claim: str) -> str:
    return claim.split(" peer financial ratio context for ", 1)[0].strip()


def _theme_from_claim(claim: str) -> str:
    return claim.rsplit(":", 1)[-1].strip() if ":" in claim else claim


def _render_peer_financial_comparison(items: list[EvidenceItem]) -> list[str]:
    peer_items = [item for item in items if item.category == "peer_financial_context"]
    lines: list[str] = []
    lines.append("## 4. US Peer Financial Comparison")
    lines.append("")
    if not peer_items:
        lines.append("- No peer financial context rows were recorded in this run.")
        lines.append("")
        return lines
    lines.append("| Symbol | Peer | Market cap | Trailing PE | Forward PE | P/B | Profit margin | Revenue growth | Debt/Equity | Current ratio | Status |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for item in sorted(peer_items, key=lambda row: (row.symbol, _peer_symbol_from_claim(row.claim))):
        metrics = _parse_semicolon_metrics(item.value)
        lines.append(
            f"| {item.symbol} | {_peer_symbol_from_claim(item.claim)} | "
            f"{metrics.get('market_cap', '')} | {metrics.get('trailing_pe', '')} | {metrics.get('forward_pe', '')} | "
            f"{metrics.get('price_to_book', '')} | {metrics.get('profit_margin', '')} | {metrics.get('revenue_growth', '')} | "
            f"{metrics.get('debt_to_equity', '')} | {metrics.get('current_ratio', '')} | {item.status} |"
        )
    lines.append("")
    lines.append("Peer table is a context lens only; business comparability and source methodology still need review before external use.")
    lines.append("")
    return lines


def _render_filing_theme_snippet_index(items: list[EvidenceItem]) -> list[str]:
    snippet_items = [item for item in items if item.category == "filing_theme_snippet"]
    lines: list[str] = []
    lines.append("## 5. US Filing Theme Snippet Index")
    lines.append("")
    if not snippet_items:
        lines.append("- No filing theme snippets were recorded in this run.")
        lines.append("")
        return lines
    lines.append("| Symbol | Theme | Claim | Source excerpt | As of | Status |")
    lines.append("|---|---|---|---|---|---|")
    for item in sorted(snippet_items, key=lambda row: (row.symbol, _theme_from_claim(row.claim))):
        lines.append(
            f"| {item.symbol} | {_theme_from_claim(item.claim)} | {_safe_table_cell(item.claim, 90)} | "
            f"{_safe_table_cell(item.value)} | {item.as_of_date} | {item.status} |"
        )
    lines.append("")
    lines.append("Snippets are keyword-selected raw filing text for researcher review; they are not interpretation or investment advice.")
    lines.append("")
    return lines


def _metric_as_float(metrics: dict[str, str], key: str) -> float | None:
    raw = metrics.get(key, "").strip()
    if not raw or raw.upper() in {"N/A", "NA", "NONE"}:
        return None
    cleaned = raw.replace(",", "").replace("%", "").replace("B", "").replace("M", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _metric_values(peer_rows: list[PeerMetricRow], key: str) -> list[tuple[float, str, str]]:
    values: list[tuple[float, str, str]] = []
    for row in peer_rows:
        peer, metrics = row[0], row[1]
        parsed = _metric_as_float(metrics, key)
        if parsed is not None:
            values.append((parsed, peer, metrics.get(key, "")))
    return values


def _metric_range(peer_rows: list[PeerMetricRow], key: str) -> str:
    values = _metric_values(peer_rows, key)
    if not values:
        return "not_available"
    low = min(values, key=lambda item: item[0])
    high = max(values, key=lambda item: item[0])
    if low[1] == high[1]:
        return f"{low[2]} ({low[1]})"
    return f"{low[2]} ({low[1]}) to {high[2]} ({high[1]})"


def _metric_spread(peer_rows: list[PeerMetricRow], key: str) -> float | None:
    values = _metric_values(peer_rows, key)
    if len(values) < 2:
        return None
    parsed_values = [value for value, _peer, _raw in values]
    return max(parsed_values) - min(parsed_values)


def _metric_ratio_spread(peer_rows: list[PeerMetricRow], key: str) -> float | None:
    values = _metric_values(peer_rows, key)
    if len(values) < 2:
        return None
    parsed_values = [value for value, _peer, _raw in values]
    low = min(parsed_values)
    high = max(parsed_values)
    if low <= 0:
        return None
    return (high - low) / abs(low)


def _crosses_absolute_threshold(peer_rows: list[PeerMetricRow], key: str, threshold: float) -> bool:
    spread = _metric_spread(peer_rows, key)
    return spread is not None and spread >= threshold


def _crosses_ratio_threshold(peer_rows: list[PeerMetricRow], key: str, threshold: float) -> bool:
    spread = _metric_ratio_spread(peer_rows, key)
    return spread is not None and spread >= threshold


def _metric_coverage(peer_rows: list[PeerMetricRow], keys: list[str]) -> str:
    missing: list[str] = []
    for peer, metrics, _item in peer_rows:
        missing_keys = [key for key in keys if _metric_as_float(metrics, key) is None]
        if missing_keys:
            missing.append(f"{peer}:missing {','.join(missing_keys)}")
    return "; ".join(missing) if missing else "all configured peer ratio fields present"


def _peer_source_summary(peer_rows: list[PeerMetricRow]) -> str:
    sources = sorted({row[2].source.split(" (info_cache=", 1)[0].strip() for row in peer_rows if row[2].source})
    if not sources:
        return "not_available"
    return "; ".join(_safe_table_cell(source, 90) for source in sources)


def _filing_question_for_theme(theme: str, evidence_basis: str) -> str:
    if theme == "business_model":
        return (
            f"Review question: Using evidence basis \"{evidence_basis}\", which revenue engine, customer segment, "
            "or competitive pressure is the controlling assumption, and which source should verify or contradict it?"
        )
    if theme == "risk_factor":
        return (
            f"Red-flag question: Using evidence basis \"{evidence_basis}\", which cited risk could invalidate the current "
            "research hypothesis, and what observable trigger would show it is worsening?"
        )
    if theme == "performance_driver":
        return (
            f"Review question: Using evidence basis \"{evidence_basis}\", which driver is recurring versus one-off, "
            "and which metric should verify it next period?"
        )
    return f"Review question: Using evidence basis \"{evidence_basis}\", what evidence would make this snippet material to the research hypothesis?"


def build_us_review_question_evidence(memo: GlobalUSResearchMemo) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    peer_rows: list[PeerMetricRow] = [
        (_peer_symbol_from_claim(item.claim), _parse_semicolon_metrics(item.value), item)
        for item in memo.evidence
        if item.category == "peer_financial_context"
    ]
    if len(peer_rows) >= 2:
        if _crosses_ratio_threshold(peer_rows, "trailing_pe", VALUATION_PE_RATIO_SPREAD_THRESHOLD) or _crosses_ratio_threshold(peer_rows, "price_to_book", VALUATION_PB_RATIO_SPREAD_THRESHOLD):
            evidence.append(EvidenceItem(
                symbol=memo.symbol,
                category="peer_review_question",
                claim=f"{memo.symbol} peer review question: valuation_vs_quality",
                value=(
                    "Red-flag question: Do trailing_pe range "
                    f"{_metric_range(peer_rows, 'trailing_pe')} or price_to_book range "
                    f"{_metric_range(peer_rows, 'price_to_book')} cross the valuation-review threshold, and which margin, growth, "
                    "segment-mix, or accounting-source evidence should explain the spread before peers are compared?"
                ),
                source="local DataOS review-rule engine from peer_financial_context",
                as_of_date=memo.generated_at[:10],
                freshness="derived_from_current_evidence",
                status="partial",
                note="Question only; derived from source-backed peer context and requires human review before external use.",
            ))
        if _crosses_absolute_threshold(peer_rows, "debt_to_equity", DEBT_TO_EQUITY_POINT_SPREAD_THRESHOLD) or _crosses_absolute_threshold(peer_rows, "current_ratio", CURRENT_RATIO_POINT_SPREAD_THRESHOLD):
            evidence.append(EvidenceItem(
                symbol=memo.symbol,
                category="peer_review_question",
                claim=f"{memo.symbol} peer review question: balance_sheet_comparability",
                value=(
                    "Review question: Do debt_to_equity range "
                    f"{_metric_range(peer_rows, 'debt_to_equity')} or current_ratio range "
                    f"{_metric_range(peer_rows, 'current_ratio')} cross the balance-sheet review threshold, and what debt maturity, cash, "
                    "working-capital, lease, or accounting evidence should normalize the comparison?"
                ),
                source="local DataOS review-rule engine from peer_financial_context",
                as_of_date=memo.generated_at[:10],
                freshness="derived_from_current_evidence",
                status="partial",
                note="Question only; balance-sheet spread is not a trade decision.",
            ))
        if _crosses_absolute_threshold(peer_rows, "profit_margin", PROFIT_MARGIN_POINT_SPREAD_THRESHOLD) or _crosses_absolute_threshold(peer_rows, "revenue_growth", REVENUE_GROWTH_POINT_SPREAD_THRESHOLD):
            evidence.append(EvidenceItem(
                symbol=memo.symbol,
                category="peer_review_question",
                claim=f"{memo.symbol} peer review question: growth_margin_quality",
                value=(
                    "Review question: Do profit_margin range "
                    f"{_metric_range(peer_rows, 'profit_margin')} and revenue_growth range "
                    f"{_metric_range(peer_rows, 'revenue_growth')} create a growth/margin comparability trigger, and which segment, "
                    "product-mix, pricing, cost-base, or one-off item evidence should be checked next?"
                ),
                source="local DataOS review-rule engine from peer_financial_context",
                as_of_date=memo.generated_at[:10],
                freshness="derived_from_current_evidence",
                status="partial",
                note="Question only; growth and margin spreads need source-backed explanation before external use.",
            ))
        evidence.append(EvidenceItem(
            symbol=memo.symbol,
            category="peer_review_question",
            claim=f"{memo.symbol} peer review question: source_methodology_check",
            value=(
                "Review question: Which source-methodology checks are needed before using peer ratios from "
                f"{_peer_source_summary(peer_rows)}—statement-period alignment, GAAP/non-GAAP definitions, currency, fiscal year, "
                f"and missing-field coverage ({_metric_coverage(peer_rows, ['trailing_pe', 'price_to_book', 'profit_margin', 'revenue_growth', 'debt_to_equity', 'current_ratio'])})?"
            ),
            source="local DataOS review-rule engine from peer_financial_context",
            as_of_date=memo.generated_at[:10],
            freshness="derived_from_current_evidence",
            status="partial",
            note="Question only; source-methodology review prevents runtime ratio fields from becoming unsupported conclusions.",
        ))

    for item in memo.evidence:
        if item.category != "filing_theme_snippet":
            continue
        theme = _theme_from_claim(item.claim)
        evidence.append(EvidenceItem(
            symbol=memo.symbol,
            category="filing_review_question",
            claim=f"{memo.symbol} filing review question: {theme}",
            value=_filing_question_for_theme(theme, _safe_table_cell(item.value, 220)),
            source="local DataOS review-rule engine from filing_theme_snippet",
            as_of_date=item.as_of_date,
            freshness="derived_from_current_evidence",
            status="partial",
            url=item.url,
            note="Question only; derived from raw filing snippet and not an interpretation or investment advice.",
        ))
    return evidence


def _render_review_question_index(items: list[EvidenceItem]) -> list[str]:
    review_items = [item for item in items if item.category in {"peer_review_question", "filing_review_question"}]
    lines: list[str] = []
    lines.append("## 6. US Review Questions / Red-Flag Checks")
    lines.append("")
    if not review_items:
        lines.append("- No derived review questions were recorded in this run.")
        lines.append("")
        return lines
    lines.append("| Symbol | Type | Claim | Question | Source | Status |")
    lines.append("|---|---|---|---|---|---|")
    for item in sorted(review_items, key=lambda row: (row.symbol, row.category, row.claim)):
        lines.append(
            f"| {item.symbol} | {item.category} | {_safe_table_cell(item.claim, 90)} | "
            f"{_safe_table_cell(item.value, 220)} | {_safe_table_cell(item.source, 70)} | {item.status} |"
        )
    lines.append("")
    lines.append("These are research questions generated from existing evidence rows; they deliberately stop before any trade decision.")
    lines.append("")
    return lines


def build_us_memos(configs: list[GlobalUSSymbolConfig], generated_at: datetime) -> list[GlobalUSResearchMemo]:
    proxy_labels = dict(DEFAULT_MACRO_PROXIES)
    for cfg in configs:
        proxy = cfg.sector_proxy or DEFAULT_SECTOR_PROXY.get(cfg.symbol, "SPY")
        proxy_labels.setdefault(proxy, DEFAULT_SECTOR_PROXY_LABELS.get(proxy, f"US sector proxy {proxy}"))
    proxy_profiles, proxy_gaps = fetch_proxy_profiles(proxy_labels)

    peer_labels = collect_peer_labels(configs)
    peer_profiles, peer_gaps = fetch_proxy_profiles(peer_labels)
    peer_financial_profiles, peer_financial_gaps = fetch_peer_financial_profiles(peer_labels)

    memos: list[GlobalUSResearchMemo] = []
    for cfg in configs:
        memo = build_global_us_memo(
            cfg,
            proxy_profiles=proxy_profiles,
            peer_profiles=peer_profiles,
            peer_financial_profiles=peer_financial_profiles,
            generated_at=generated_at,
        )
        memo.evidence.extend(build_us_review_question_evidence(memo))
        for gap in proxy_gaps + peer_gaps + peer_financial_gaps:
            if gap not in memo.evidence_gaps:
                memo.evidence_gaps.append(gap)
        memos.append(memo)
    return memos


def build_china_memos(configs: list[ChinaSymbolConfig], generated_at: datetime) -> list[ChinaResearchMemo]:
    return [build_china_memo(cfg, generated_at=generated_at) for cfg in configs]


def render_us_china_report(
    us_memos: list[GlobalUSResearchMemo],
    china_memos: list[ChinaResearchMemo],
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    us_items = _collect_evidence(us_memos)
    china_items = _collect_evidence(china_memos)
    all_items = us_items + china_items
    lane_summaries = [_summarize_lane("US", us_memos), _summarize_lane("China", china_memos)]
    status_counts = _status_counts(all_items)
    category_counts = _category_counts(all_items)
    gaps = _all_gaps("US", us_memos) + _all_gaps("China", china_memos)

    lines: list[str] = []
    lines.append("# US + China Pilot Research Memo")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("")
    lines.append("- Current priority: US-first Global core. For now, Global means the US research mainline; other global markets are deferred.")
    lines.append("- Parallel branch: China market data remains active under the same Evidence Ledger contract.")
    lines.append("- Objective: prove both US and China can run in one local research workflow before adding more markets.")
    lines.append("- Decision boundary: information collection, structured analysis, evidence gaps, and research suggestions only; no trade decision, no position sizing, no execution.")
    lines.append("")
    lines.append("## 2. Lane Summary")
    lines.append("")
    lines.append("| Lane | Symbols | Evidence items | OK items | Review items / gaps |")
    lines.append("|---|---:|---:|---:|---:|")
    for summary in lane_summaries:
        lines.append(f"| {summary.lane} | {summary.symbols} | {summary.evidence_items} | {summary.ok_items} | {summary.review_items_or_gaps} |")
    lines.append("")
    lines.append("## 3. Evidence Health")
    lines.append("")
    lines.append(f"- Total evidence items: {len(all_items)}")
    lines.append(f"- Status counts: `{json.dumps(status_counts, ensure_ascii=False)}`")
    lines.append(f"- Category counts: `{json.dumps(category_counts, ensure_ascii=False)}`")
    lines.append(f"- Explicit evidence gaps: {len(gaps)}")
    lines.append("")
    lines.extend(_render_peer_financial_comparison(us_items))
    lines.extend(_render_filing_theme_snippet_index(us_items))
    lines.extend(_render_review_question_index(us_items))
    lines.append("## 7. US Core Cards")
    lines.append("")
    for memo in us_memos:
        lines.append(f"### {memo.symbol} {memo.name}".rstrip())
        lines.append(f"- Asset type: `{memo.asset_type}`")
        lines.append(f"- Sector proxy: `{memo.sector_proxy}`")
        lines.append(f"- Evidence items: {len(memo.evidence)}")
        lines.append(f"- OK items: {memo.ok_count}")
        lines.append(f"- Review issues/gaps: {memo.issue_count}")
        lines.append("")
    lines.append("## 8. China Parallel Cards")
    lines.append("")
    for memo in china_memos:
        title = f"{memo.symbol} {memo.name}".strip()
        lines.append(f"### {title}")
        lines.append(f"- Asset type: `{memo.asset_type}`")
        lines.append(f"- Evidence items: {len(memo.evidence)}")
        lines.append(f"- OK items: {memo.ok_count}")
        lines.append(f"- Review issues/gaps: {memo.issue_count}")
        lines.append("")
    lines.append("## 9. Evidence Gaps")
    lines.append("")
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- No explicit evidence gaps were recorded in this run.")
    lines.append("")
    lines.append("## 10. Research Queue")
    lines.append("")
    lines.append("- US first: refine review-rule thresholds, add cache coverage for remaining sources, and prepare source-aligned external report template.")
    lines.append("- China parallel: configure Tushare token, run real AKShare/Tushare reconciliation, cache source responses, and compare dates/close fields.")
    lines.append("- Cross-lane: keep one Evidence Ledger schema before adding other Global markets.")
    lines.append("")
    lines.append("## 11. Decision Boundary")
    lines.append("")
    lines.append("本报告不输出买入、卖出、持有或仓位建议。任何交易决策应由使用者自行完成。")
    lines.append("")
    return "\n".join(lines)


def _public_text(value: str, limit: int | None = None) -> str:
    text = " ".join(str(value).split()).replace("|", "/")
    text = re.sub(r";?\s*(info_cache|markdown_cache|sections_cache)=[^;]+", "", text)
    text = re.sub(r"\.cache/[^\s;,]+", "source-cache", text)
    text = text.replace("local DataOS review-rule engine", "Evidence Ledger review-rule engine")
    text = text.replace("local DataOS reconciliation gate", "Evidence Ledger reconciliation gate")
    text = text.replace("local DataOS", "Evidence Ledger")
    text = text.replace("blocked_by_tushare_token_missing", "Tushare credential missing; dual-source reconciliation not completed")
    text = text.replace("token_missing", "Tushare credential missing")
    text = text.replace("no FMP_API_KEY in environment; using toolkit fallback where available", "provider credential not configured; fallback data used where available")
    if limit is not None and len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _public_source(source: str) -> str:
    source = source.split(" (info_cache=", 1)[0]
    source = source.split(" (markdown_cache=", 1)[0]
    source = source.split(" (sections_cache=", 1)[0]
    source = source.replace("local DataOS review-rule engine from", "derived review rules from")
    source = source.replace("local DataOS reconciliation gate", "Evidence Ledger reconciliation gate")
    source = source.replace("local DataOS", "Evidence Ledger")
    return _public_text(source, 120)


def _public_sources(items: list[EvidenceItem], limit: int = 3) -> str:
    sources: list[str] = []
    for item in items:
        public = _public_source(item.source)
        if public and public not in sources:
            sources.append(public)
        if len(sources) >= limit:
            break
    return "; ".join(sources) if sources else "not recorded"


def _status_summary(items: list[EvidenceItem]) -> str:
    counts = _status_counts(items)
    ordered = [f"{status} {count}" for status, count in counts.items()]
    return "; ".join(ordered) if ordered else "no rows"


def _latest_dates(items: list[EvidenceItem], limit: int = 3) -> str:
    dates = sorted({item.as_of_date for item in items if item.as_of_date and item.as_of_date != "n/a"}, reverse=True)
    return ", ".join(dates[:limit]) if dates else "not recorded"


def _area_items(items: list[EvidenceItem], categories: set[str]) -> list[EvidenceItem]:
    return [item for item in items if item.category in categories]


def _render_external_source_coverage(items: list[EvidenceItem]) -> list[str]:
    area_specs = [
        (
            "Price / market data",
            {"price", "liquidity", "macro_sector_context", "peer_set_context", "china_price", "china_liquidity", "china_index", "china_etf_structure"},
            "Public market feeds can be delayed or adjusted differently by provider.",
        ),
        (
            "Financial metrics",
            {"fundamentals", "profitability", "valuation", "financial_health", "peer_financial_context"},
            "Ratio definitions and statement periods need source-methodology review.",
        ),
        (
            "Filings / announcements",
            {"filing", "filing_deep_read", "filing_excerpt", "filing_theme_snippet"},
            "Filing snippets are source excerpts for review, not interpretation.",
        ),
        (
            "Review questions",
            {"peer_review_question", "filing_review_question"},
            "Derived question layer only; not a source fact.",
        ),
        (
            "Public expert signals",
            EXPERT_SIGNAL_CATEGORIES,
            "Angle-discovery lane only; public expert signals remain unverified until primary or auditable sources are inspected.",
        ),
        (
            "Expert source verification",
            EXPERT_SOURCE_VERIFICATION_CATEGORIES,
            "Auditable source-check lane; verifies only the narrow source claim and keeps remaining gaps visible.",
        ),
        (
            "China source reconciliation",
            {"china_data_source", "china_reconciliation"},
            "Dual-source check depends on AKShare and Tushare availability.",
        ),
    ]
    lines = ["| Evidence area | Source used | As-of / freshness | Coverage | Caveat |", "|---|---|---|---|---|"]
    for area, categories, caveat in area_specs:
        rows = _area_items(items, categories)
        if not rows:
            lines.append(f"| {area} | not recorded | not recorded | 0 rows | {caveat} |")
            continue
        lines.append(
            f"| {area} | {_public_sources(rows)} | {_latest_dates(rows)} | {len(rows)} rows; {_status_summary(rows)} | {caveat} |"
        )
    return lines


def _symbol_lane(symbol_items: list[EvidenceItem]) -> str:
    if any(item.category in EXPERT_DISCUSSION_CATEGORIES for item in symbol_items):
        return "Expert signal / source-check lane"
    if any(item.category.startswith("china_") for item in symbol_items):
        return "China parallel branch"
    return "US-first core"


def _first_matching_item(items: list[EvidenceItem], categories: set[str], claim_contains: str | None = None) -> EvidenceItem | None:
    for item in items:
        if item.category not in categories:
            continue
        if claim_contains and claim_contains.lower() not in item.claim.lower():
            continue
        return item
    return None


def _symbol_snapshot_metric(symbol_items: list[EvidenceItem]) -> str:
    item = _first_matching_item(symbol_items, {"price", "china_price", "china_index"}, "latest")
    if item is None:
        item = _first_matching_item(symbol_items, {"fundamentals", "valuation", "china_etf_structure"})
    if item is None:
        item = _first_matching_item(symbol_items, EXPERT_DISCUSSION_CATEGORIES)
    if item is None:
        return "not recorded"
    return f"{_public_text(item.claim, 70)}: {_public_text(item.value, 60)}"


def _symbol_main_question(symbol_items: list[EvidenceItem]) -> str:
    item = _first_matching_item(symbol_items, {"peer_review_question", "filing_review_question", "expert_signal_review_question"})
    if item is None:
        return "No derived review question recorded."
    return _public_text(item.value, 180)


def _render_external_snapshot(items: list[EvidenceItem]) -> list[str]:
    by_symbol: dict[str, list[EvidenceItem]] = {}
    for item in items:
        by_symbol.setdefault(item.symbol, []).append(item)
    lines = ["| Symbol | Lane | Latest public metric | Evidence coverage | Main review question |", "|---|---|---|---|---|"]
    for symbol in sorted(by_symbol):
        rows = by_symbol[symbol]
        counts = _status_counts(rows)
        coverage = f"{len(rows)} rows; ok {counts.get('ok', 0)}, partial {counts.get('partial', 0)}, missing {counts.get('missing', 0)}"
        lines.append(
            f"| {symbol} | {_symbol_lane(rows)} | {_symbol_snapshot_metric(rows)} | {coverage} | {_symbol_main_question(rows)} |"
        )
    return lines


def _external_observations(items: list[EvidenceItem]) -> list[str]:
    symbols = sorted({item.symbol for item in items})
    categories = _category_counts(items)
    us_symbols = sorted({item.symbol for item in items if not item.category.startswith("china_") and item.category not in EXPERT_DISCUSSION_CATEGORIES})
    china_symbols = sorted({item.symbol for item in items if item.category.startswith("china_")})
    missing_rows = [item for item in items if item.status == "missing"]
    expert_rows = [item for item in items if item.category in EXPERT_SIGNAL_CATEGORIES]
    source_verification_rows = [item for item in items if item.category in EXPERT_SOURCE_VERIFICATION_CATEGORIES]
    lines = [
        f"- Evidence ledger contains {len(items)} rows across {len(symbols)} symbols; status coverage is {_status_summary(items)}.",
        f"- US-first core covers {', '.join(us_symbols) if us_symbols else 'no US symbols'} with price, financial, filing, peer context, and review-question rows where available.",
        f"- China parallel branch covers {', '.join(china_symbols) if china_symbols else 'no China symbols'} under the same ledger schema.",
        f"- Review layer contains {categories.get('peer_review_question', 0)} peer questions, {categories.get('filing_review_question', 0)} filing questions, and {categories.get('expert_signal_review_question', 0)} public expert-signal questions; they are derived prompts for human review.",
    ]
    if expert_rows:
        lines.append(f"- Public expert signal layer contributes {len(expert_rows)} rows as angle discovery and counterview inputs; each remains not yet verified by primary evidence until a source check is completed.")
    if source_verification_rows:
        ok_checks = sum(1 for item in source_verification_rows if item.status == "ok")
        gap_checks = sum(1 for item in source_verification_rows if item.status == "missing")
        lines.append(f"- Source verification layer contributes {len(source_verification_rows)} auditable-source rows; {ok_checks} are checked source supports and {gap_checks} remain explicit verification gaps.")
    if any("TUSHARE_TOKEN" in (item.claim + item.value + item.note) for item in missing_rows):
        lines.append("- China dual-source reconciliation is not complete because TUSHARE_TOKEN is not configured; AKShare evidence remains present, while Tushare-backed comparison is still a source gap.")
    return lines


def _next_source_for_question(item: EvidenceItem) -> str:
    if item.category == "expert_signal_review_question":
        return "primary or auditable source, evidence-ledger support/conflict check, and counterview"
    claim = item.claim.lower()
    if "valuation_vs_quality" in claim:
        return "segment mix, margin, growth, and accounting-method evidence"
    if "balance_sheet" in claim:
        return "debt maturity, cash, working-capital, lease, and accounting notes"
    if "growth_margin" in claim:
        return "segment revenue, pricing, cost-base, and one-off item checks"
    if "source_methodology" in claim:
        return "provider methodology and statement-period alignment"
    if "business_model" in claim:
        return "segment, customer, and revenue-source evidence"
    if "risk_factor" in claim:
        return "risk section, observable trigger, and latest external data"
    if "performance_driver" in claim:
        return "MD&A metric and next-period verification source"
    return "source evidence and human review"


def _render_external_questions(items: list[EvidenceItem]) -> list[str]:
    question_items = [item for item in items if item.category in {"peer_review_question", "filing_review_question", "expert_signal_review_question"}]
    lines = ["| Symbol | Type | Question | Evidence basis / next source | Status |", "|---|---|---|---|---|"]
    if not question_items:
        lines.append("| - | - | No derived review questions recorded. | - | - |")
        return lines
    for item in sorted(question_items, key=lambda row: (row.symbol, row.category, row.claim)):
        question_type = item.claim.split(": ", 1)[-1]
        lines.append(
            f"| {item.symbol} | {_public_text(question_type, 70)} | {_public_text(item.value, 240)} | {_next_source_for_question(item)} | {item.status} |"
        )
    return lines


def _render_external_gaps(items: list[EvidenceItem]) -> list[str]:
    hard_gaps = [item for item in items if item.status == "missing"]
    partial_count = sum(1 for item in items if item.status == "partial")
    lines: list[str] = []
    if hard_gaps:
        lines.extend(["| Symbol | Gap | Source | Status |", "|---|---|---|---|"])
        for item in sorted(hard_gaps, key=lambda row: (row.symbol, row.category, row.claim)):
            gap = _public_text(f"{item.claim}: {item.value}. {item.note}", 220)
            lines.append(f"| {item.symbol} | {gap} | {_public_source(item.source)} | {item.status} |")
    else:
        lines.append("- No hard source gap recorded in this run.")
    if partial_count:
        lines.append(f"- Partial rows: {partial_count}. Most are derived review questions or method-sensitive context rows that still need human review.")
    return lines


def render_external_research_note(items: list[EvidenceItem], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    status_counts = _status_counts(items)
    category_counts = _category_counts(items)
    symbols = sorted({item.symbol for item in items})

    lines: list[str] = []
    lines.append("# Investment Research Note / 投研参考报告")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("## 1. Reader Context & Scope")
    lines.append("")
    lines.append("- Research scope: US-first core plus China parallel branch, under one Evidence Ledger schema.")
    lines.append(f"- Symbols covered: {', '.join(symbols) if symbols else 'not recorded'}.")
    lines.append("- Out of scope: concrete trade instruction, portfolio allocation, broker execution, or return promise.")
    lines.append("- Reader action: use the evidence and questions below to decide what source checks are still needed.")
    lines.append("")
    lines.append("## 2. Source Freshness & Evidence Coverage")
    lines.append("")
    lines.extend(_render_external_source_coverage(items))
    lines.append("")
    lines.append("## 3. Snapshot")
    lines.append("")
    lines.extend(_render_external_snapshot(items))
    lines.append("")
    lines.append("## 4. Evidence Ledger Summary")
    lines.append("")
    lines.append(f"- Total evidence rows: {len(items)}")
    lines.append(f"- Status counts: `{json.dumps(status_counts, ensure_ascii=False)}`")
    lines.append(f"- Category counts: `{json.dumps(category_counts, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 5. Evidence-Backed Observations")
    lines.append("")
    lines.extend(_external_observations(items))
    lines.append("")
    expert_items = [item for item in items if item.category in EXPERT_SIGNAL_CATEGORIES]
    if expert_items:
        expert_crosswalk = render_public_expert_signal_crosswalk(expert_items, generated_at=generated_at)
        crosswalk_body = expert_crosswalk.split("\n", 6)[-1]
        lines.append("## 6. Public Expert Signal Crosswalk")
        lines.append("")
        lines.append(crosswalk_body)
        lines.append("")
    source_verification_items = [item for item in items if item.category in EXPERT_SOURCE_VERIFICATION_CATEGORIES]
    if source_verification_items:
        source_crosswalk = render_source_verification_crosswalk(source_verification_items, generated_at=generated_at)
        source_crosswalk_body = source_crosswalk.split("\n", 6)[-1]
        lines.append("## 7. Source Verification Crosswalk")
        lines.append("")
        lines.append(source_crosswalk_body)
        lines.append("")
    lines.append("## 8. Research Questions / Red-Flag Checks")
    lines.append("")
    lines.extend(_render_external_questions(items))
    lines.append("")
    lines.append("## 9. Evidence Gaps & Source Caveats")
    lines.append("")
    lines.extend(_render_external_gaps(items))
    lines.append("")
    lines.append("## 10. Next Research Actions")
    lines.append("")
    lines.append("- Verify peer-ratio source methodology before comparing valuation, quality, growth, or balance-sheet signals.")
    lines.append("- Complete Tushare credential setup before treating China dual-source reconciliation as complete.")
    lines.append("- Read the cited filing sections directly before turning snippets into an interpretation.")
    lines.append("- Cross-check public expert signals against filings, financial metrics, primary sources, and counterevidence before using them as observations.")
    lines.append("- For source-verified expert signals, inspect the remaining unproven claims before upgrading from support/gap to research observation.")
    lines.append("- Replace sample symbols with the actual intake list before preparing a personalized reference note.")
    lines.append("")
    lines.append("## 11. Decision Boundary")
    lines.append("")
    lines.append("本报告只支持信息整理、证据核验、风险讨论和下一步研究安排，不提供具体交易指令、仓位安排或收益承诺。")
    lines.append("")
    return "\n".join(lines)


def scan_external_note_quality(text: str) -> dict[str, int]:
    lower_text = text.lower()
    result = {f"decision:{phrase}": lower_text.count(phrase.lower()) for phrase in EXTERNAL_NOTE_FORBIDDEN_PHRASES}
    result.update({f"hype:{phrase}": lower_text.count(phrase.lower()) for phrase in EXTERNAL_NOTE_HYPE_PHRASES})
    result.update({f"leak:{marker}": lower_text.count(marker.lower()) for marker in EXTERNAL_NOTE_FORBIDDEN_MARKERS})
    return result


def scan_boundary(text: str) -> dict[str, int]:
    lower_text = text.lower()
    return {phrase: lower_text.count(phrase.lower()) for phrase in FORBIDDEN_REPORT_PHRASES}


def run(
    us_symbols: list[str],
    china_symbols: list[str],
    out_dir: Path,
    expert_signal_seed_paths: list[Path] | None = None,
    source_verification_seed_paths: list[Path] | None = None,
) -> USChinaPilotResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    us_configs = [parse_us_symbol_arg(raw) for raw in us_symbols]
    china_configs = [parse_china_symbol_arg(raw) for raw in china_symbols]

    us_memos = build_us_memos(us_configs, generated_at=generated_at)
    china_memos = build_china_memos(china_configs, generated_at=generated_at)
    expert_items = load_expert_signal_seeds(expert_signal_seed_paths or [])
    source_verification_items = load_source_verification_seeds(source_verification_seed_paths or [])
    all_items = _collect_evidence(us_memos) + _collect_evidence(china_memos) + expert_items + source_verification_items
    report = render_us_china_report(us_memos, china_memos, generated_at=generated_at)
    external_note = render_external_research_note(all_items, generated_at=generated_at)
    boundary_scan = scan_boundary(report)
    external_quality_scan = scan_external_note_quality(external_note)

    report_path = out_dir / "us_china_pilot_memo.md"
    ledger_csv_path = out_dir / "us_china_evidence_ledger.csv"
    ledger_json_path = out_dir / "us_china_evidence_ledger.json"
    boundary_scan_path = out_dir / "boundary_scan.json"
    external_note_path = out_dir / "external_research_note.md"
    external_quality_scan_path = out_dir / "external_note_quality_scan.json"

    write_ledger(all_items, ledger_csv_path, ledger_json_path)
    report_path.write_text(report, encoding="utf-8")
    external_note_path.write_text(external_note, encoding="utf-8")
    boundary_scan_path.write_text(json.dumps(boundary_scan, ensure_ascii=False, indent=2), encoding="utf-8")
    external_quality_scan_path.write_text(json.dumps(external_quality_scan, ensure_ascii=False, indent=2), encoding="utf-8")

    if any(count > 0 for count in boundary_scan.values()):
        raise RuntimeError(f"Forbidden decision phrase found: {boundary_scan}")
    external_nonzero = {marker: count for marker, count in external_quality_scan.items() if count}
    if external_nonzero:
        raise RuntimeError(f"External note quality scan failed: {external_nonzero}")

    return USChinaPilotResult(
        report_path=report_path,
        ledger_csv_path=ledger_csv_path,
        ledger_json_path=ledger_json_path,
        boundary_scan_path=boundary_scan_path,
        external_note_path=external_note_path,
        external_quality_scan_path=external_quality_scan_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one US-first + China-parallel pilot workflow.")
    parser.add_argument("--us-symbols", nargs="+", default=DEFAULT_US_SYMBOLS, help="US symbols as SYMBOL[:asset_type[:sector_proxy[:name]]].")
    parser.add_argument("--china-symbols", nargs="+", default=DEFAULT_CHINA_SYMBOLS, help="China symbols as code[:asset_type[:name]].")
    parser.add_argument("--expert-signal-seeds", nargs="*", type=Path, default=[], help="CSV seed file(s) for public expert signal Evidence Ledger rows.")
    parser.add_argument("--source-verification-seeds", nargs="*", type=Path, default=[], help="CSV seed file(s) for auditable source verification rows tied to expert signals.")
    parser.add_argument("--out", type=Path, default=Path("reports/us-china-pilot"))
    args = parser.parse_args(argv)

    result = run(
        args.us_symbols,
        args.china_symbols,
        args.out,
        expert_signal_seed_paths=args.expert_signal_seeds,
        source_verification_seed_paths=args.source_verification_seeds,
    )
    print(f"report={result.report_path}")
    print(f"ledger_csv={result.ledger_csv_path}")
    print(f"ledger_json={result.ledger_json_path}")
    print(f"boundary_scan={result.boundary_scan_path}")
    print(f"external_note={result.external_note_path}")
    print(f"external_quality_scan={result.external_quality_scan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
