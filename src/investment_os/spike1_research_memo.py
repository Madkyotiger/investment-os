from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .pipeline import DISCLAIMER, sanitize_suggestion


@dataclass
class EvidenceItem:
    symbol: str
    category: str
    claim: str
    value: str
    source: str
    as_of_date: str
    freshness: str
    status: str
    url: str = ""
    note: str = ""


@dataclass
class SymbolResearchMemo:
    symbol: str
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
class Spike1RunResult:
    report_path: Path
    ledger_csv_path: Path
    ledger_json_path: Path


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except Exception:
        return None


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:.4g}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _freshness_from_date(as_of: str, stale_after_days: int) -> str:
    try:
        parsed = date.fromisoformat(str(as_of)[:10])
    except Exception:
        return "unknown"
    age = (datetime.now(timezone.utc).date() - parsed).days
    if age < 0:
        return "future_date_check"
    if age <= stale_after_days:
        return "fresh"
    return f"stale_{age}d"


def _as_date_string(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        parsed = pd.to_datetime(value)
        if pd.isna(parsed):
            return "n/a"
        return parsed.date().isoformat()
    except Exception:
        return str(value)[:10]


def _add_gap(memo: SymbolResearchMemo, gap: str) -> None:
    if gap not in memo.evidence_gaps:
        memo.evidence_gaps.append(gap)


def _value_from_frame(df: pd.DataFrame, row_candidates: Iterable[str]) -> tuple[str, float | None] | None:
    if df is None or df.empty:
        return None
    index_labels = [str(idx) for idx in df.index]
    label_map = {label.lower(): original for label, original in zip(index_labels, df.index)}
    for candidate in row_candidates:
        key = candidate.lower()
        if key not in label_map:
            continue
        row = df.loc[label_map[key]]
        row = row.dropna()
        if row.empty:
            return None
        latest_col = row.index[-1]
        return str(latest_col), _safe_float(row.iloc[-1])
    return None


def fetch_openbb_price_evidence(symbol: str) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        from openbb import obb

        start_date = (datetime.now(timezone.utc).date() - timedelta(days=390)).isoformat()
        output = obb.equity.price.historical(symbol, provider="yfinance", start_date=start_date)
        df = output.to_dataframe()
        if df is None or df.empty:
            gaps.append("OpenBB/yfinance returned no historical price rows.")
            return evidence, gaps

        close_col = "close" if "close" in df.columns else "Close" if "Close" in df.columns else None
        volume_col = "volume" if "volume" in df.columns else "Volume" if "Volume" in df.columns else None
        if close_col is None:
            gaps.append("OpenBB price data did not include a close column.")
            return evidence, gaps

        last_row = df.dropna(subset=[close_col]).tail(1)
        if last_row.empty:
            gaps.append("OpenBB price data close column was empty.")
            return evidence, gaps
        latest_idx = last_row.index[-1]
        latest_date = _as_date_string(latest_idx)
        latest_close = _safe_float(last_row[close_col].iloc[0])
        latest_volume = _safe_float(last_row[volume_col].iloc[0]) if volume_col else None

        close_series = df[close_col].dropna()
        ret_1y = None
        if len(close_series) > 200:
            first = _safe_float(close_series.iloc[0])
            last = _safe_float(close_series.iloc[-1])
            if first and last:
                ret_1y = last / first - 1.0

        freshness = _freshness_from_date(latest_date, stale_after_days=7)
        status = "ok" if freshness == "fresh" else "stale"
        evidence.append(EvidenceItem(
            symbol=symbol,
            category="price",
            claim="Latest adjusted close from OpenBB yfinance provider",
            value=_format_number(latest_close),
            source="OpenBB.equity.price.historical(provider=yfinance)",
            as_of_date=latest_date,
            freshness=freshness,
            status=status,
            note="OpenBB used as the global data/tooling base for this spike.",
        ))
        evidence.append(EvidenceItem(
            symbol=symbol,
            category="price",
            claim="Approximate trailing one-year price return from OpenBB history",
            value=_format_pct(ret_1y),
            source="OpenBB.equity.price.historical(provider=yfinance)",
            as_of_date=latest_date,
            freshness=freshness,
            status="ok" if ret_1y is not None and status == "ok" else "partial",
        ))
        if latest_volume is not None:
            evidence.append(EvidenceItem(
                symbol=symbol,
                category="liquidity",
                claim="Latest reported daily volume from OpenBB yfinance provider",
                value=_format_number(latest_volume),
                source="OpenBB.equity.price.historical(provider=yfinance)",
                as_of_date=latest_date,
                freshness=freshness,
                status=status,
            ))
    except Exception as exc:
        gaps.append(f"OpenBB price adapter failed: {type(exc).__name__}: {exc}")
    return evidence, gaps


def fetch_financetoolkit_evidence(symbol: str) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        from financetoolkit import Toolkit

        api_key = os.getenv("FMP_API_KEY") or None
        toolkit = Toolkit([symbol], api_key=api_key, start_date="2022-01-01")
        income_statement = toolkit.get_income_statement()
        profitability = toolkit.ratios.collect_profitability_ratios()

        source_note = "FinanceToolkit"
        if not api_key:
            source_note += " (no FMP_API_KEY in environment; using toolkit fallback where available)"

        revenue = _value_from_frame(income_statement, ["Revenue", "Operating Revenue"])
        operating_income = _value_from_frame(income_statement, ["Operating Income"])
        net_income = _value_from_frame(income_statement, ["Net Income", "Net Income Common Stockholders"])

        for label, result, category in [
            ("Latest annual revenue", revenue, "fundamentals"),
            ("Latest annual operating income", operating_income, "fundamentals"),
            ("Latest annual net income", net_income, "fundamentals"),
        ]:
            if result is None:
                gaps.append(f"FinanceToolkit did not return {label.lower()}.")
                continue
            period, value = result
            evidence.append(EvidenceItem(
                symbol=symbol,
                category=category,
                claim=label,
                value=_format_number(value),
                source=source_note,
                as_of_date=str(period),
                freshness="annual_statement",
                status="ok" if value is not None else "missing",
                note="Financial statement line item; review source methodology before external use.",
            ))

        for label in ["Gross Margin", "Operating Margin", "Net Profit Margin"]:
            result = _value_from_frame(profitability, [label])
            if result is None:
                gaps.append(f"FinanceToolkit did not return {label}.")
                continue
            period, value = result
            evidence.append(EvidenceItem(
                symbol=symbol,
                category="ratio",
                claim=label,
                value=_format_pct(value),
                source=source_note,
                as_of_date=str(period),
                freshness="annual_ratio",
                status="ok" if value is not None else "missing",
                note="Ratio generated by FinanceToolkit for transparent calculation review.",
            ))
    except Exception as exc:
        gaps.append(f"FinanceToolkit adapter failed: {type(exc).__name__}: {exc}")
    return evidence, gaps


def fetch_edgar_filing_evidence(symbol: str) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        from edgar import Company, set_identity

        identity = (os.getenv("SEC_EDGAR_IDENTITY") or "").strip()
        if not identity:
            return evidence, ["SEC_EDGAR_IDENTITY is not configured; SEC lookup skipped."]
        set_identity(identity)
        company = Company(symbol)
        for form, stale_after in [("10-K", 540), ("10-Q", 190), ("8-K", 120), ("4", 190)]:
            try:
                filing = company.get_filings(form=form).latest(1)
            except Exception as exc:
                gaps.append(f"edgartools did not return latest {form}: {type(exc).__name__}: {exc}")
                continue
            if not filing:
                gaps.append(f"edgartools returned no latest {form} filing.")
                continue
            filing_date = _as_date_string(getattr(filing, "filing_date", None))
            freshness = _freshness_from_date(filing_date, stale_after_days=stale_after)
            status = "ok" if freshness == "fresh" or freshness.startswith("stale_") is False else "stale"
            # 10-K filings naturally age over a year; keep them usable unless very old.
            if freshness.startswith("stale_") and form in {"10-K", "10-Q"}:
                status = "partial"
            evidence.append(EvidenceItem(
                symbol=symbol,
                category="filing",
                claim=f"Latest SEC {form} filing metadata",
                value=f"{getattr(filing, 'company', symbol)} {form} filed {filing_date}",
                source="edgartools.Company.get_filings",
                as_of_date=filing_date,
                freshness=freshness,
                status=status,
                url=getattr(filing, "filing_url", "") or getattr(filing, "homepage_url", ""),
                note=f"accession={getattr(filing, 'accession_no', '')}; primary_document={getattr(filing, 'primary_document', '')}",
            ))
    except Exception as exc:
        gaps.append(f"edgartools adapter failed: {type(exc).__name__}: {exc}")
    return evidence, gaps


def build_symbol_memo(symbol: str, generated_at: datetime | None = None) -> SymbolResearchMemo:
    generated_at = generated_at or datetime.now(timezone.utc)
    memo = SymbolResearchMemo(symbol=symbol, generated_at=generated_at.isoformat())

    for fetcher in (fetch_openbb_price_evidence, fetch_financetoolkit_evidence, fetch_edgar_filing_evidence):
        evidence, gaps = fetcher(symbol)
        memo.evidence.extend(evidence)
        for gap in gaps:
            _add_gap(memo, gap)

    suggestions = [
        "建议核对最新财报口径：收入、利润率、现金流和同业对比是否一致。",
        "建议补充最近一期 10-K/10-Q 的风险因素、管理层讨论和关键事件。",
        "建议形成反方 thesis：哪些宏观、行业或公司事件会推翻当前研究假设。",
        "建议把该标的纳入组合风险复核：集中度、相关性、回撤和币种/市场暴露。",
    ]
    memo.research_suggestions = [sanitize_suggestion(item) for item in suggestions]
    if not memo.evidence:
        _add_gap(memo, "No evidence item was collected; do not use this memo externally.")
    return memo


def flatten_evidence(memos: Iterable[SymbolResearchMemo]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for memo in memos:
        items.extend(memo.evidence)
    return items


def write_ledger(items: list[EvidenceItem], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(items[0]).keys()) if items else list(EvidenceItem("", "", "", "", "", "", "", "").__dict__.keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))
    json_path.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2), encoding="utf-8")


def render_research_memo(memos: list[SymbolResearchMemo], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    evidence_items = flatten_evidence(memos)
    ok_count = sum(1 for item in evidence_items if item.status == "ok")
    issue_count = sum(1 for item in evidence_items if item.status != "ok") + sum(len(m.evidence_gaps) for m in memos)

    lines: list[str] = []
    lines.append("# Spike 1 Research Memo — OpenBB / FinanceToolkit / edgartools")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("")
    lines.append("- Goal: prove the first professional-analysis mainline with real data and source-backed evidence.")
    lines.append("- Data/tooling base: OpenBB with yfinance provider for market data.")
    lines.append("- Professional-analysis base: FinanceToolkit for financial statements and ratios; edgartools for SEC filing metadata.")
    lines.append("- Decision boundary: research memo only; no trade decision, no position sizing, no execution.")
    lines.append("")
    lines.append("## 2. Data Quality Summary")
    lines.append("")
    lines.append(f"- Symbols: {len(memos)}")
    lines.append(f"- Evidence items: {len(evidence_items)}")
    lines.append(f"- OK items: {ok_count}")
    lines.append(f"- Items/gaps needing review: {issue_count}")
    lines.append("")

    for memo in memos:
        lines.append(f"## 3. {memo.symbol} Research Card")
        lines.append("")
        lines.append(f"- Evidence items: {len(memo.evidence)}")
        lines.append(f"- OK items: {memo.ok_count}")
        lines.append(f"- Review issues/gaps: {memo.issue_count}")
        lines.append("")
        lines.append("### Evidence Ledger Extract")
        lines.append("")
        lines.append("| Category | Claim | Value | Source | As of | Freshness | Status |")
        lines.append("|---|---|---:|---|---|---|---|")
        for item in memo.evidence:
            source = item.source.replace("|", "/")
            claim = item.claim.replace("|", "/")
            value = item.value.replace("|", "/")
            lines.append(f"| {item.category} | {claim} | {value} | {source} | {item.as_of_date} | {item.freshness} | {item.status} |")
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

    lines.append("## 4. Integration Verdict")
    lines.append("")
    lines.append("- OpenBB, FinanceToolkit, and edgartools can enter the Phase 1 mainline as source-backed modules.")
    lines.append("- External modules still do not own the final report. The local DataOS owns evidence status, report schema, and boundary policy.")
    lines.append("- If a field is missing, stale, or conflicting, the report must say so instead of letting an LLM fill the gap.")
    lines.append("")
    lines.append("## 5. Decision Boundary")
    lines.append("")
    lines.append("本报告不输出买入、卖出、持有或仓位建议。任何交易决策应由使用者自行完成。")
    lines.append("")
    return "\n".join(lines)


def run(symbols: list[str], out_dir: Path) -> Spike1RunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    memos = [build_symbol_memo(symbol.strip().upper(), generated_at=generated_at) for symbol in symbols]
    report = render_research_memo(memos, generated_at=generated_at)
    report_path = out_dir / "research_memo.md"
    ledger_csv_path = out_dir / "evidence_ledger.csv"
    ledger_json_path = out_dir / "evidence_ledger.json"
    write_ledger(flatten_evidence(memos), ledger_csv_path, ledger_json_path)
    report_path.write_text(report, encoding="utf-8")
    return Spike1RunResult(report_path=report_path, ledger_csv_path=ledger_csv_path, ledger_json_path=ledger_json_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Spike 1 source-backed research memo pipeline.")
    parser.add_argument("--symbols", nargs="+", default=["AAPL", "MSFT"], help="US symbols to research")
    parser.add_argument("--out", type=Path, default=Path("reports/spike-1"))
    args = parser.parse_args(argv)
    result = run(args.symbols, args.out)
    print(f"report={result.report_path}")
    print(f"ledger_csv={result.ledger_csv_path}")
    print(f"ledger_json={result.ledger_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
