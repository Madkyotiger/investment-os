from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .pipeline import DISCLAIMER, sanitize_suggestion
from . import source_cache
from .spike1_research_memo import (
    EvidenceItem,
    _as_date_string,
    _format_number,
    _format_pct,
    _freshness_from_date,
    _safe_float,
    _value_from_frame,
    fetch_edgar_filing_evidence,
    fetch_openbb_price_evidence,
    write_ledger,
)

DEFAULT_SECTOR_PROXY = {
    "AAPL": "XLK",
    "MSFT": "XLK",
    "NVDA": "XLK",
    "GOOGL": "XLC",
    "GOOG": "XLC",
    "META": "XLC",
    "AMZN": "XLY",
    "TSLA": "XLY",
    "JPM": "XLF",
    "BAC": "XLF",
    "XOM": "XLE",
    "CVX": "XLE",
    "JNJ": "XLV",
    "LLY": "XLV",
    "PG": "XLP",
    "COST": "XLP",
}

DEFAULT_MACRO_PROXIES = {
    "SPY": "US large-cap equity proxy",
    "QQQ": "US growth / Nasdaq proxy",
    "TLT": "US long-duration Treasury proxy",
    "UUP": "US dollar proxy",
}

DEFAULT_SECTOR_PROXY_LABELS = {
    "XLK": "US technology sector proxy",
    "XLC": "US communication services sector proxy",
    "XLY": "US consumer discretionary sector proxy",
    "XLF": "US financials sector proxy",
    "XLE": "US energy sector proxy",
    "XLV": "US health care sector proxy",
    "XLP": "US consumer staples sector proxy",
    "XLI": "US industrials sector proxy",
    "XLB": "US materials sector proxy",
    "XLU": "US utilities sector proxy",
    "XLRE": "US real estate sector proxy",
}

DEFAULT_PEER_SETS = {
    "AAPL": ["MSFT", "GOOGL", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "AMZN"],
    "NVDA": ["AMD", "AVGO", "TSM"],
    "GOOGL": ["META", "MSFT", "AMZN"],
    "GOOG": ["META", "MSFT", "AMZN"],
    "AMZN": ["WMT", "COST", "GOOGL"],
}


@dataclass
class GlobalUSSymbolConfig:
    symbol: str
    asset_type: str = "equity"
    sector_proxy: str = ""
    name: str = ""


@dataclass
class GlobalUSResearchMemo:
    symbol: str
    asset_type: str
    sector_proxy: str
    name: str
    generated_at: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    research_suggestions: list[str] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for item in self.evidence if item.status == "ok")

    @property
    def issue_count(self) -> int:
        return sum(1 for item in self.evidence if item.status != "ok") + len(self.evidence_gaps)


@dataclass
class ProxyProfile:
    symbol: str
    label: str
    latest_close: float | None
    return_60d: float | None
    return_1y: float | None
    latest_date: str
    freshness: str
    status: str
    source: str = "OpenBB.equity.price.historical(provider=yfinance)"


@dataclass
class PeerFinancialProfile:
    symbol: str
    label: str
    as_of_date: str
    status: str
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    profit_margin: float | None = None
    revenue_growth: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    source: str = "yfinance.Ticker.info"


@dataclass
class Spike11RunResult:
    report_path: Path
    ledger_csv_path: Path
    ledger_json_path: Path


def _add_gap(memo: GlobalUSResearchMemo, gap: str) -> None:
    if gap not in memo.evidence_gaps:
        memo.evidence_gaps.append(gap)


def parse_symbol_arg(raw: str) -> GlobalUSSymbolConfig:
    """Parse SYMBOL[:asset_type[:sector_proxy[:name]]]."""
    parts = raw.split(":")
    symbol = parts[0].strip().upper()
    if not symbol:
        raise ValueError("empty symbol")
    asset_type = parts[1].strip().lower() if len(parts) >= 2 and parts[1].strip() else "equity"
    sector_proxy = parts[2].strip().upper() if len(parts) >= 3 and parts[2].strip() else DEFAULT_SECTOR_PROXY.get(symbol, "SPY")
    name = parts[3].strip() if len(parts) >= 4 and parts[3].strip() else ""
    return GlobalUSSymbolConfig(symbol=symbol, asset_type=asset_type, sector_proxy=sector_proxy, name=name)


def _calc_return(close: pd.Series, days: int) -> float | None:
    close = close.dropna()
    if len(close) <= days:
        return None
    start = _safe_float(close.iloc[-days - 1])
    end = _safe_float(close.iloc[-1])
    if start is None or end is None or start == 0:
        return None
    return end / start - 1.0


def _fetch_openbb_history(symbol: str, start_days: int = 430) -> tuple[pd.DataFrame | None, list[str]]:
    gaps: list[str] = []
    try:
        from openbb import obb

        start_date = (datetime.now(timezone.utc).date() - timedelta(days=start_days)).isoformat()
        output = obb.equity.price.historical(symbol, provider="yfinance", start_date=start_date)
        df = output.to_dataframe()
        if df is None or df.empty:
            return None, [f"OpenBB/yfinance returned no rows for {symbol}."]
        return df, gaps
    except Exception as exc:
        return None, [f"OpenBB/yfinance failed for {symbol}: {type(exc).__name__}: {exc}"]


def fetch_proxy_profiles(proxy_labels: dict[str, str]) -> tuple[dict[str, ProxyProfile], list[str]]:
    profiles: dict[str, ProxyProfile] = {}
    gaps: list[str] = []
    for proxy, label in proxy_labels.items():
        df, proxy_gaps = _fetch_openbb_history(proxy)
        if proxy_gaps:
            gaps.extend(proxy_gaps)
        if df is None or df.empty:
            continue
        close_col = "close" if "close" in df.columns else "Close" if "Close" in df.columns else None
        if close_col is None:
            gaps.append(f"OpenBB/yfinance data for {proxy} has no close column.")
            continue
        close = df[close_col].dropna()
        if close.empty:
            gaps.append(f"OpenBB/yfinance close data for {proxy} is empty.")
            continue
        latest_date = _as_date_string(close.index[-1])
        freshness = _freshness_from_date(latest_date, stale_after_days=7)
        status = "ok" if freshness == "fresh" else "stale"
        profiles[proxy] = ProxyProfile(
            symbol=proxy,
            label=label,
            latest_close=_safe_float(close.iloc[-1]),
            return_60d=_calc_return(close, 60),
            return_1y=_calc_return(close, min(252, len(close) - 2)),
            latest_date=latest_date,
            freshness=freshness,
            status=status,
        )
    return profiles, gaps


def build_macro_sector_evidence(
    cfg: GlobalUSSymbolConfig,
    profiles: dict[str, ProxyProfile],
) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    needed = ["SPY", cfg.sector_proxy or DEFAULT_SECTOR_PROXY.get(cfg.symbol, "SPY"), "TLT", "UUP"]
    seen: set[str] = set()
    for proxy in needed:
        if not proxy or proxy in seen:
            continue
        seen.add(proxy)
        profile = profiles.get(proxy)
        if profile is None:
            gaps.append(f"Macro/sector proxy {proxy} is missing for {cfg.symbol}.")
            continue
        evidence.append(EvidenceItem(
            symbol=cfg.symbol,
            category="macro_sector_context",
            claim=f"{profile.symbol} context: {profile.label}",
            value=(
                f"close={_format_number(profile.latest_close)}; "
                f"60D={_format_pct(profile.return_60d)}; "
                f"1Y={_format_pct(profile.return_1y)}"
            ),
            source=profile.source,
            as_of_date=profile.latest_date,
            freshness=profile.freshness,
            status=profile.status,
            note="Context lens only; not a trading signal.",
        ))
    return evidence, gaps


def default_peers_for_symbol(symbol: str) -> list[str]:
    return list(DEFAULT_PEER_SETS.get(symbol.upper(), []))


def collect_peer_labels(configs: Iterable[GlobalUSSymbolConfig]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for cfg in configs:
        for peer in default_peers_for_symbol(cfg.symbol):
            if peer.upper() == cfg.symbol.upper():
                continue
            labels.setdefault(peer, f"US equity peer for {cfg.symbol}")
    return labels


def build_peer_set_evidence(
    cfg: GlobalUSSymbolConfig,
    peer_profiles: dict[str, ProxyProfile],
) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    peers = default_peers_for_symbol(cfg.symbol)
    if not peers:
        gaps.append(f"No default peer set configured for {cfg.symbol}.")
        return evidence, gaps

    for peer in peers:
        profile = peer_profiles.get(peer)
        if profile is None:
            gaps.append(f"Peer profile {peer} is missing for {cfg.symbol}.")
            continue
        evidence.append(EvidenceItem(
            symbol=cfg.symbol,
            category="peer_set_context",
            claim=f"{profile.symbol} peer context for {cfg.symbol}",
            value=(
                f"close={_format_number(profile.latest_close)}; "
                f"60D={_format_pct(profile.return_60d)}; "
                f"1Y={_format_pct(profile.return_1y)}"
            ),
            source=profile.source,
            as_of_date=profile.latest_date,
            freshness=profile.freshness,
            status=profile.status,
            note=(
                f"Peer map source=local DataOS default peer set; label={profile.label}; "
                "context lens only; not a trading signal. Verify business comparability before external use."
            ),
        ))
    return evidence, gaps


def _metric_count(profile: PeerFinancialProfile) -> int:
    return sum(
        value is not None
        for value in (
            profile.market_cap,
            profile.trailing_pe,
            profile.forward_pe,
            profile.price_to_book,
            profile.profit_margin,
            profile.revenue_growth,
            profile.debt_to_equity,
            profile.current_ratio,
        )
    )


def _cached_yfinance_info(symbol: str) -> tuple[dict[str, Any] | None, str, str | None]:
    runtime_date = datetime.now(timezone.utc).date().isoformat()
    key = source_cache.cache_key("yfinance_info", symbol.upper(), runtime_date)
    cached, path = source_cache.read_json("yfinance_info", key, ".json")
    if cached is not None:
        return dict(cached), f"info_cache=hit:{path}", None
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        selected_keys = {
            "marketCap",
            "trailingPE",
            "forwardPE",
            "priceToBook",
            "profitMargins",
            "revenueGrowth",
            "debtToEquity",
            "currentRatio",
        }
        selected = {key_name: info.get(key_name) for key_name in selected_keys}
        source_cache.write_json("yfinance_info", key, selected, ".json")
        return selected, f"info_cache=miss:{path}", None
    except Exception as exc:
        return None, f"info_cache=error:{path}", f"yfinance info failed for {symbol}: {type(exc).__name__}: {exc}"


def fetch_peer_financial_profiles(peer_labels: dict[str, str]) -> tuple[dict[str, PeerFinancialProfile], list[str]]:
    profiles: dict[str, PeerFinancialProfile] = {}
    gaps: list[str] = []
    runtime_date = datetime.now(timezone.utc).date().isoformat()
    for peer, label in peer_labels.items():
        info, cache_note, error = _cached_yfinance_info(peer)
        if error:
            gaps.append(error)
            continue
        info = info or {}
        profile = PeerFinancialProfile(
            symbol=peer,
            label=label,
            as_of_date=runtime_date,
            status="missing",
            market_cap=_safe_float(info.get("marketCap")),
            trailing_pe=_safe_float(info.get("trailingPE")),
            forward_pe=_safe_float(info.get("forwardPE")),
            price_to_book=_safe_float(info.get("priceToBook")),
            profit_margin=_safe_float(info.get("profitMargins")),
            revenue_growth=_safe_float(info.get("revenueGrowth")),
            debt_to_equity=_safe_float(info.get("debtToEquity")),
            current_ratio=_safe_float(info.get("currentRatio")),
        )
        count = _metric_count(profile)
        profile.status = "ok" if count >= 4 else "partial" if count > 0 else "missing"
        profile.source = f"yfinance.Ticker.info ({cache_note})"
        if count == 0:
            gaps.append(f"yfinance info returned no financial ratio fields for peer {peer}.")
            continue
        profiles[peer] = profile
    return profiles, gaps


def build_peer_financial_evidence(
    cfg: GlobalUSSymbolConfig,
    peer_financial_profiles: dict[str, PeerFinancialProfile],
) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    peers = default_peers_for_symbol(cfg.symbol)
    if not peers:
        gaps.append(f"No default peer financial set configured for {cfg.symbol}.")
        return evidence, gaps

    for peer in peers:
        profile = peer_financial_profiles.get(peer)
        if profile is None:
            gaps.append(f"Peer financial profile {peer} is missing for {cfg.symbol}.")
            continue
        evidence.append(EvidenceItem(
            symbol=cfg.symbol,
            category="peer_financial_context",
            claim=f"{profile.symbol} peer financial ratio context for {cfg.symbol}",
            value=(
                f"market_cap={_format_number(profile.market_cap)}; "
                f"trailing_pe={_format_number(profile.trailing_pe)}; "
                f"forward_pe={_format_number(profile.forward_pe)}; "
                f"price_to_book={_format_number(profile.price_to_book)}; "
                f"profit_margin={_format_pct(profile.profit_margin)}; "
                f"revenue_growth={_format_pct(profile.revenue_growth)}; "
                f"debt_to_equity={_format_number(profile.debt_to_equity)}; "
                f"current_ratio={_format_number(profile.current_ratio)}"
            ),
            source=profile.source,
            as_of_date=profile.as_of_date,
            freshness="runtime_financial_profile",
            status=profile.status,
            note=(
                f"Peer map source=local DataOS default peer set; label={profile.label}; "
                "financial-ratio context only; not a trading signal. yfinance info has no statement-period guarantee; verify before external use."
            ),
        ))
    return evidence, gaps


def fetch_financial_hardening_evidence(symbol: str) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        from financetoolkit import Toolkit

        api_key = os.getenv("FMP_API_KEY") or None
        toolkit = Toolkit([symbol], api_key=api_key, start_date="2022-01-01")
        source_note = "FinanceToolkit"
        if not api_key:
            source_note += " (no FMP_API_KEY in environment; using toolkit fallback where available)"

        frames: dict[str, pd.DataFrame] = {}
        collectors: dict[str, Any] = {
            "income": toolkit.get_income_statement,
            "profitability": toolkit.ratios.collect_profitability_ratios,
            "valuation": toolkit.ratios.collect_valuation_ratios,
            "solvency": toolkit.ratios.collect_solvency_ratios,
            "liquidity": toolkit.ratios.collect_liquidity_ratios,
        }
        for name, fn in collectors.items():
            try:
                frames[name] = fn()
            except Exception as exc:
                gaps.append(f"FinanceToolkit {name} collector failed for {symbol}: {type(exc).__name__}: {exc}")
                frames[name] = pd.DataFrame()

        metric_specs = [
            ("fundamentals", "Latest annual revenue", "income", ["Revenue", "Operating Revenue"], "number"),
            ("fundamentals", "Latest annual operating income", "income", ["Operating Income"], "number"),
            ("fundamentals", "Latest annual net income", "income", ["Net Income", "Net Income Common Stockholders"], "number"),
            ("profitability", "Gross Margin", "profitability", ["Gross Margin"], "pct"),
            ("profitability", "Operating Margin", "profitability", ["Operating Margin"], "pct"),
            ("profitability", "Net Profit Margin", "profitability", ["Net Profit Margin"], "pct"),
            ("valuation", "Price-to-Earnings", "valuation", ["Price-to-Earnings"], "number"),
            ("valuation", "Price-to-Book", "valuation", ["Price-to-Book"], "number"),
            ("financial_health", "Debt-to-Equity Ratio", "solvency", ["Debt-to-Equity Ratio"], "number"),
            ("financial_health", "Current Ratio", "liquidity", ["Current Ratio"], "number"),
        ]

        for category, label, frame_name, row_candidates, fmt in metric_specs:
            result = _value_from_frame(frames.get(frame_name, pd.DataFrame()), row_candidates)
            if result is None:
                gaps.append(f"FinanceToolkit did not return {label} for {symbol}.")
                continue
            period, value = result
            evidence.append(EvidenceItem(
                symbol=symbol,
                category=category,
                claim=label,
                value=_format_pct(value) if fmt == "pct" else _format_number(value),
                source=source_note,
                as_of_date=str(period),
                freshness="annual_financial_metric",
                status="ok" if value is not None else "missing",
                note="Metric is calculated by FinanceToolkit; verify methodology before external distribution.",
            ))
    except Exception as exc:
        gaps.append(f"FinanceToolkit hardening adapter failed for {symbol}: {type(exc).__name__}: {exc}")
    return evidence, gaps


def _latest_annual_filing(symbol: str) -> tuple[Any | None, list[str]]:
    gaps: list[str] = []
    try:
        from edgar import Company, set_identity

        identity = (os.getenv("SEC_EDGAR_IDENTITY") or "").strip()
        if not identity:
            return None, ["SEC_EDGAR_IDENTITY is not configured; SEC lookup skipped."]
        set_identity(identity)
        company = Company(symbol)
        for form in ("10-K", "20-F"):
            try:
                filing = company.get_filings(form=form).latest(1)
                if filing:
                    return filing, gaps
            except Exception as exc:
                gaps.append(f"edgartools did not return latest {form} for {symbol}: {type(exc).__name__}: {exc}")
        return None, gaps or [f"No annual SEC filing found for {symbol}."]
    except Exception as exc:
        return None, [f"edgartools annual filing lookup failed for {symbol}: {type(exc).__name__}: {exc}"]


def _filing_section_targets(form: str) -> dict[str, str]:
    if form == "20-F":
        return {
            "3D": "Risk Factors",
            "4": "Information on the Company",
            "5": "Operating and Financial Review",
        }
    return {
        "1": "Business",
        "1A": "Risk Factors",
        "7": "Management Discussion and Analysis",
    }


def _clean_section_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u2019", "'")).strip()


def _label_tokens(label: str) -> list[str]:
    lower = label.lower().replace("management discussion", "management discussion")
    if "risk" in lower:
        return ["risk", "factor"]
    if "management" in lower:
        return ["management", "discussion"]
    if "business" in lower or "information on the company" in lower:
        return ["business"] if "business" in lower else ["information", "company"]
    if "operating" in lower:
        return ["operating", "financial"]
    return [token for token in re.split(r"\W+", lower) if token]


def _item_heading_match(text: str) -> re.Match[str] | None:
    cleaned = _clean_section_text(text).lstrip("# ")
    return re.match(r"(?i)^item\s+([0-9]+[a-z]?)\.?\s*(.*)$", cleaned)


def _is_section_boundary(text: str) -> bool:
    match = _item_heading_match(text)
    if not match:
        return False
    # Ignore repeated page headers such as "Item 1" inside extracted sections.
    return bool(match.group(2).strip())


def _matches_target_heading(text: str, item: str, label: str) -> tuple[bool, str]:
    match = _item_heading_match(text)
    if not match or match.group(1).upper() != item.upper():
        return False, ""
    cleaned = _clean_section_text(text)
    probe = cleaned[:260].lower()
    tokens = _label_tokens(label)
    return all(token in probe for token in tokens), cleaned[:160]


def _extract_item_section_bodies_from_markdown(markdown: str) -> dict[str, tuple[str, str]]:
    heading_re = re.compile(r"(?im)^#{1,6}\s+Item\s+([0-9]+[A-Z]?)\.?\s+(.+?)\s*$")
    matches = list(heading_re.finditer(markdown))
    sections: dict[str, tuple[str, str]] = {}
    for i, match in enumerate(matches):
        item = match.group(1).upper()
        title = _clean_section_text(match.group(2))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = _clean_section_text(markdown[start:end])
        sections[item] = (title, body)
    return sections


def _extract_item_sections_from_markdown(markdown: str) -> dict[str, tuple[str, int]]:
    return {item: (title, len(body)) for item, (title, body) in _extract_item_section_bodies_from_markdown(markdown).items()}


def _extract_item_section_bodies_from_chunks(chunks: list[str], targets: dict[str, str]) -> dict[str, tuple[str, str]]:
    cleaned_chunks = [_clean_section_text(chunk) for chunk in chunks if _clean_section_text(chunk)]
    sections: dict[str, tuple[str, str]] = {}
    for item, label in targets.items():
        for idx, chunk in enumerate(cleaned_chunks):
            matched, title = _matches_target_heading(chunk, item, label)
            if not matched:
                continue
            end_idx = len(cleaned_chunks)
            for next_idx in range(idx + 1, len(cleaned_chunks)):
                if _is_section_boundary(cleaned_chunks[next_idx]):
                    end_idx = next_idx
                    break
            body = _clean_section_text("\n".join(cleaned_chunks[idx:end_idx]))
            sections[item.upper()] = (title, body)
            break
    return sections


def _extract_item_sections_from_chunks(chunks: list[str], targets: dict[str, str]) -> dict[str, tuple[str, int]]:
    return {item: (title, len(body)) for item, (title, body) in _extract_item_section_bodies_from_chunks(chunks, targets).items()}


def _extract_item_section_bodies(markdown: str, chunks: list[str] | None = None, targets: dict[str, str] | None = None) -> dict[str, tuple[str, str]]:
    targets = targets or _filing_section_targets("10-K")
    sections = _extract_item_section_bodies_from_markdown(markdown)
    if chunks:
        chunk_sections = _extract_item_section_bodies_from_chunks(chunks, targets)
        for item, value in chunk_sections.items():
            # Prefer chunk extraction when markdown headings are missing or suspiciously short.
            if item not in sections or len(value[1]) > len(sections[item][1]):
                sections[item] = value
    return sections


def _extract_item_sections(markdown: str, chunks: list[str] | None = None, targets: dict[str, str] | None = None) -> dict[str, tuple[str, int]]:
    return {item: (title, len(body)) for item, (title, body) in _extract_item_section_bodies(markdown, chunks=chunks, targets=targets).items()}


def _short_filing_excerpt(body: str, limit: int = 520) -> str:
    cleaned = _clean_section_text(body)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "…"


FILING_THEME_SPECS_10K = {
    "1": ("business_model", ["revenue", "products", "services", "customers", "segment", "platform", "competition", "business"]),
    "1A": ("risk_factor", ["risk", "adverse", "material", "regulatory", "competition", "cybersecurity", "supply", "depend"]),
    "7": ("performance_driver", ["revenue", "net sales", "margin", "income", "demand", "expenses", "cash", "segment", "increase", "decrease"]),
}

FILING_THEME_SPECS_20F = {
    "3D": FILING_THEME_SPECS_10K["1A"],
    "4": FILING_THEME_SPECS_10K["1"],
    "5": FILING_THEME_SPECS_10K["7"],
}


def _filing_theme_specs(form: str) -> dict[str, tuple[str, list[str]]]:
    return FILING_THEME_SPECS_20F if form == "20-F" else FILING_THEME_SPECS_10K


def _split_review_sentences(body: str) -> list[str]:
    cleaned = _clean_section_text(body)
    if not cleaned:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z#])", cleaned) if part.strip()]
    if len(sentences) <= 1:
        return [cleaned]
    return sentences


def _select_theme_snippet(body: str, keywords: list[str], limit: int = 520) -> str:
    sentences = _split_review_sentences(body)
    if not sentences:
        return ""

    noise_terms = [
        "table of contents",
        "financial statements and supplementary data",
        "index to financial statements",
        "form 10-k",
        "income statements |",
        ":-------------",
    ]

    def is_noise(sentence: str) -> bool:
        lower = sentence.lower()
        return any(term in lower for term in noise_terms) or sentence.count("|") >= 4

    candidates = [sentence for sentence in sentences if not is_noise(sentence)] or sentences

    def score(sentence: str) -> int:
        lower = sentence.lower()
        keyword_hits = sum(lower.count(keyword.lower()) for keyword in keywords)
        noise = sum(3 for term in noise_terms if term in lower)
        if is_noise(sentence):
            noise += 100
        if len(sentence) < 80:
            noise += 1
        return keyword_hits * 5 - noise

    best_idx = max(range(len(candidates)), key=lambda idx: (score(candidates[idx]), min(len(candidates[idx]), limit)))
    if score(candidates[best_idx]) <= 0:
        return _short_filing_excerpt(" ".join(candidates), limit=limit)

    selected: list[str] = []
    total = 0
    for sentence in candidates[best_idx:]:
        selected.append(sentence)
        total += len(sentence) + 1
        if total >= limit * 0.75:
            break
    candidate = " ".join(selected)
    return _short_filing_excerpt(candidate, limit=limit)


def build_theme_filing_snippet_evidence(
    symbol: str,
    form: str,
    filing_date: str,
    section_bodies: dict[str, tuple[str, str]],
    url: str,
    accession: str,
    cache_note: str,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for item, (theme, keywords) in _filing_theme_specs(form).items():
        section = section_bodies.get(item.upper())
        if section is None:
            continue
        actual_title, body = section
        snippet = _select_theme_snippet(body, keywords)
        if not snippet:
            continue
        evidence.append(EvidenceItem(
            symbol=symbol,
            category="filing_theme_snippet",
            claim=f"{form} Item {item} theme snippet: {theme}",
            value=snippet,
            source=f"edgartools.Filing.markdown+sections(form={form})",
            as_of_date=filing_date,
            freshness="annual_filing_theme_snippet",
            status="ok" if len(snippet) >= 160 else "partial",
            url=url,
            note=(
                f"theme_keywords={','.join(keywords)}; actual_title={actual_title}; accession={accession}; {cache_note}; "
                "keyword-selected raw filing snippet for researcher review; not an interpretation or recommendation."
            ),
        ))
    return evidence


def _cached_filing_markdown_and_sections(symbol: str, filing: Any, form: str) -> tuple[str | None, list[str], list[str], str]:
    accession = getattr(filing, "accession_no", "unknown")
    key = source_cache.cache_key(symbol, form, accession, getattr(filing, "primary_document", ""))
    gaps: list[str] = []
    cache_notes: list[str] = []

    markdown, markdown_path = source_cache.read_text("sec_filing_markdown", key, ".md")
    if markdown is None:
        try:
            markdown = filing.markdown()
            if markdown:
                source_cache.write_text("sec_filing_markdown", key, markdown, ".md")
            cache_notes.append(f"markdown_cache=miss:{markdown_path}")
        except Exception as exc:
            markdown = None
            gaps.append(f"edgartools markdown extraction failed for {symbol}: {type(exc).__name__}: {exc}")
    else:
        cache_notes.append(f"markdown_cache=hit:{markdown_path}")

    cached_sections, sections_path = source_cache.read_json("sec_filing_sections", key, ".json")
    if cached_sections is None:
        try:
            raw_sections = filing.sections()
            sections = [str(section) for section in raw_sections]
            source_cache.write_json("sec_filing_sections", key, sections, ".json")
            cache_notes.append(f"sections_cache=miss:{sections_path}")
        except Exception as exc:
            sections = []
            gaps.append(f"edgartools section extraction failed for {symbol}: {type(exc).__name__}: {exc}")
    else:
        sections = [str(section) for section in cached_sections]
        cache_notes.append(f"sections_cache=hit:{sections_path}")

    return markdown, sections, gaps, "; ".join(cache_notes)


def fetch_filing_deep_read_evidence(symbol: str) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    filing, filing_gaps = _latest_annual_filing(symbol)
    gaps.extend(filing_gaps)
    if filing is None:
        return evidence, gaps

    form = getattr(filing, "form", "annual")
    filing_date = _as_date_string(getattr(filing, "filing_date", None))
    url = getattr(filing, "filing_url", "") or getattr(filing, "homepage_url", "")
    markdown, section_chunks, cache_gaps, cache_note = _cached_filing_markdown_and_sections(symbol, filing, form)
    gaps.extend(cache_gaps)
    if not markdown and not section_chunks:
        gaps.append(f"edgartools returned no markdown or section chunks for {symbol} {form}.")
        return evidence, gaps

    targets = _filing_section_targets(form)
    section_bodies = _extract_item_section_bodies(markdown or "", chunks=section_chunks, targets=targets)
    for item, label in targets.items():
        section = section_bodies.get(item.upper())
        if section is None:
            gaps.append(f"{symbol} {form} section Item {item} {label} was not found in markdown/sections.")
            continue
        actual_title, body = section
        char_count = len(body)
        evidence.append(EvidenceItem(
            symbol=symbol,
            category="filing_deep_read",
            claim=f"{form} Item {item} section detected: {label}",
            value=f"section_found; chars={char_count}",
            source=f"edgartools.Filing.markdown+sections(form={form})",
            as_of_date=filing_date,
            freshness="annual_filing_section",
            status="ok" if char_count > 500 else "partial",
            url=url,
            note=(
                f"actual_title={actual_title}; accession={getattr(filing, 'accession_no', '')}; {cache_note}; "
                "content not summarized here to avoid hallucinated filing interpretation."
            ),
        ))
        excerpt = _short_filing_excerpt(body)
        if excerpt:
            evidence.append(EvidenceItem(
                symbol=symbol,
                category="filing_excerpt",
                claim=f"{form} Item {item} source excerpt: {label}",
                value=excerpt,
                source=f"edgartools.Filing.markdown+sections(form={form})",
                as_of_date=filing_date,
                freshness="annual_filing_excerpt",
                status="ok" if len(excerpt) >= 160 else "partial",
                url=url,
                note=(
                    f"actual_title={actual_title}; accession={getattr(filing, 'accession_no', '')}; {cache_note}; "
                    "raw filing excerpt for researcher review; not an interpretation or recommendation."
                ),
            ))
    evidence.extend(build_theme_filing_snippet_evidence(
        symbol=symbol,
        form=form,
        filing_date=filing_date,
        section_bodies=section_bodies,
        url=url,
        accession=getattr(filing, "accession_no", ""),
        cache_note=cache_note,
    ))
    return evidence, gaps


def build_global_us_memo(
    cfg: GlobalUSSymbolConfig,
    proxy_profiles: dict[str, ProxyProfile],
    peer_profiles: dict[str, ProxyProfile] | None = None,
    peer_financial_profiles: dict[str, PeerFinancialProfile] | None = None,
    generated_at: datetime | None = None,
) -> GlobalUSResearchMemo:
    generated_at = generated_at or datetime.now(timezone.utc)
    memo = GlobalUSResearchMemo(
        symbol=cfg.symbol,
        asset_type=cfg.asset_type,
        sector_proxy=cfg.sector_proxy,
        name=cfg.name,
        generated_at=generated_at.isoformat(),
    )

    for fetcher in (fetch_openbb_price_evidence, fetch_financial_hardening_evidence, fetch_edgar_filing_evidence, fetch_filing_deep_read_evidence):
        evidence, gaps = fetcher(cfg.symbol)
        memo.evidence.extend(evidence)
        for gap in gaps:
            _add_gap(memo, gap)

    macro_evidence, macro_gaps = build_macro_sector_evidence(cfg, proxy_profiles)
    memo.evidence.extend(macro_evidence)
    for gap in macro_gaps:
        _add_gap(memo, gap)

    if peer_profiles is not None:
        peer_evidence, peer_gaps = build_peer_set_evidence(cfg, peer_profiles)
        memo.evidence.extend(peer_evidence)
        for gap in peer_gaps:
            _add_gap(memo, gap)

    if peer_financial_profiles is not None:
        peer_financial_evidence, peer_financial_gaps = build_peer_financial_evidence(cfg, peer_financial_profiles)
        memo.evidence.extend(peer_financial_evidence)
        for gap in peer_financial_gaps:
            _add_gap(memo, gap)

    memo.evidence.append(EvidenceItem(
        symbol=cfg.symbol,
        category="hypothesis_seed",
        claim="Research hypothesis seed generated from evidence requirements",
        value="needs_validation_against_price_financial_filing_macro_and_peer_evidence",
        source="local DataOS policy",
        as_of_date=generated_at.date().isoformat(),
        freshness="generated_from_current_evidence",
        status="partial",
        note="This is a research queue seed, not an investment decision.",
    ))

    memo.research_suggestions = [
        sanitize_suggestion("建议核对价格、财务、filing、宏观/行业四类证据是否互相支持或互相冲突。"),
        sanitize_suggestion("建议深读最新 10-K/10-Q 或 20-F 的 business、risk factors 和 MD&A，再形成研究假设。"),
        sanitize_suggestion("建议核对同业 peer financial ratio table：估值、盈利能力、增长、财务健康和行业 ETF 表现是否同向或背离。"),
        sanitize_suggestion("建议记录反方 thesis：哪些 filing 风险、宏观变量或竞争变化会推翻当前研究路径。"),
    ]
    if not memo.evidence:
        _add_gap(memo, "No Global/US evidence was collected; do not use this memo externally.")
    return memo


def flatten_evidence(memos: Iterable[GlobalUSResearchMemo]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for memo in memos:
        items.extend(memo.evidence)
    return items


def render_global_us_memo(memos: list[GlobalUSResearchMemo], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    items = flatten_evidence(memos)
    ok_count = sum(1 for item in items if item.status == "ok")
    partial_or_missing = sum(1 for item in items if item.status != "ok")
    gap_count = sum(len(memo.evidence_gaps) for memo in memos)

    lines: list[str] = []
    lines.append("# Spike 1.1 Global/US Hardening Memo")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("")
    lines.append("- Goal: harden the Global/US core while keeping China as a parallel branch in the same Evidence Ledger contract.")
    lines.append("- Global/US core: OpenBB/yfinance prices, FinanceToolkit financial metrics, edgartools SEC filing metadata/section detection/source excerpts, macro/sector ETF context, default peer-set price context, and peer financial-ratio context.")
    lines.append("- China branch: remains parallel through Spike 2 AKShare/Tushare outputs; not replaced and not treated as secondary.")
    lines.append("- Decision boundary: research memo only; no trade decision, no position sizing, no execution.")
    lines.append("")
    lines.append("## 2. Data Quality Summary")
    lines.append("")
    lines.append(f"- Symbols: {len(memos)}")
    lines.append(f"- Evidence items: {len(items)}")
    lines.append(f"- OK items: {ok_count}")
    lines.append(f"- Partial/missing/stale items: {partial_or_missing}")
    lines.append(f"- Explicit evidence gaps: {gap_count}")
    lines.append("")

    for memo in memos:
        title = f"{memo.symbol} {memo.name}".strip()
        lines.append(f"## 3. {title} Global/US Research Card")
        lines.append("")
        lines.append(f"- Asset type: `{memo.asset_type}`")
        lines.append(f"- Sector proxy: `{memo.sector_proxy}`")
        lines.append(f"- Evidence items: {len(memo.evidence)}")
        lines.append(f"- OK items: {memo.ok_count}")
        lines.append(f"- Review issues/gaps: {memo.issue_count}")
        lines.append("")
        lines.append("### Evidence Ledger Extract")
        lines.append("")
        lines.append("| Category | Claim | Value | Source | As of | Freshness | Status |")
        lines.append("|---|---|---:|---|---|---|---|")
        for item in memo.evidence:
            lines.append(
                f"| {item.category} | {item.claim.replace('|', '/')} | {item.value.replace('|', '/')} | "
                f"{item.source.replace('|', '/')} | {item.as_of_date} | {item.freshness} | {item.status} |"
            )
        lines.append("")
        if memo.evidence_gaps:
            lines.append("### Evidence Gaps")
            lines.append("")
            for gap in memo.evidence_gaps:
                lines.append(f"- {gap}")
            lines.append("")
        lines.append("### Research Suggestions")
        lines.append("")
        for suggestion in memo.research_suggestions:
            lines.append(f"- {suggestion}")
        lines.append("")

    lines.append("## 4. Two-Lane Verdict")
    lines.append("")
    lines.append("- Global/US and China are both important; the system should run them as two data branches under one DataOS contract.")
    lines.append("- Global/US is the near-term hardening priority because US equities need filing depth, financial quality checks, macro/sector context, and peer comparison.")
    lines.append("- China data remains active as a parallel branch and should continue through source hardening, token-gated Tushare, cache, and field reconciliation.")
    lines.append("")
    lines.append("## 5. Decision Boundary")
    lines.append("")
    lines.append("本报告不输出买入、卖出、持有或仓位建议。任何交易决策应由使用者自行完成。")
    lines.append("")
    return "\n".join(lines)


def run(configs: list[GlobalUSSymbolConfig], out_dir: Path) -> Spike11RunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    proxy_labels = dict(DEFAULT_MACRO_PROXIES)
    for cfg in configs:
        proxy = cfg.sector_proxy or DEFAULT_SECTOR_PROXY.get(cfg.symbol, "SPY")
        proxy_labels.setdefault(proxy, DEFAULT_SECTOR_PROXY_LABELS.get(proxy, f"US sector proxy {proxy}"))
    proxy_profiles, proxy_gaps = fetch_proxy_profiles(proxy_labels)
    peer_labels = collect_peer_labels(configs)
    peer_profiles, peer_gaps = fetch_proxy_profiles(peer_labels)
    peer_financial_profiles, peer_financial_gaps = fetch_peer_financial_profiles(peer_labels)
    memos = []
    for cfg in configs:
        memo = build_global_us_memo(
            cfg,
            proxy_profiles=proxy_profiles,
            peer_profiles=peer_profiles,
            peer_financial_profiles=peer_financial_profiles,
            generated_at=generated_at,
        )
        for gap in proxy_gaps + peer_gaps + peer_financial_gaps:
            _add_gap(memo, gap)
        memos.append(memo)

    report_path = out_dir / "global_us_hardening_memo.md"
    ledger_csv_path = out_dir / "global_us_evidence_ledger.csv"
    ledger_json_path = out_dir / "global_us_evidence_ledger.json"
    write_ledger(flatten_evidence(memos), ledger_csv_path, ledger_json_path)
    report_path.write_text(render_global_us_memo(memos, generated_at=generated_at), encoding="utf-8")
    return Spike11RunResult(report_path=report_path, ledger_csv_path=ledger_csv_path, ledger_json_path=ledger_json_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Spike 1.1 Global/US hardening memo pipeline.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["AAPL:equity:XLK:Apple", "MSFT:equity:XLK:Microsoft", "NVDA:equity:XLK:NVIDIA", "GOOGL:equity:XLC:Alphabet", "AMZN:equity:XLY:Amazon"],
        help="Symbols as SYMBOL[:asset_type[:sector_proxy[:name]]].",
    )
    parser.add_argument("--out", type=Path, default=Path("reports/spike-1-1"))
    args = parser.parse_args(argv)
    configs = [parse_symbol_arg(raw) for raw in args.symbols]
    result = run(configs, args.out)
    print(f"report={result.report_path}")
    print(f"ledger_csv={result.ledger_csv_path}")
    print(f"ledger_json={result.ledger_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
