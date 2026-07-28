from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import DISCLAIMER, sanitize_suggestion
from .spike1_research_memo import EvidenceItem, write_ledger


@dataclass
class ChinaSymbolConfig:
    symbol: str
    asset_type: str = "etf"
    name: str = ""


@dataclass
class ChinaResearchMemo:
    symbol: str
    asset_type: str
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
class Spike2RunResult:
    report_path: Path
    ledger_csv_path: Path
    ledger_json_path: Path


def classify_convenience_evidence(items: list[EvidenceItem]) -> None:
    for item in items:
        source = item.source.lower()
        if source.startswith("akshare"):
            item.source_authority = "convenience_secondary"
            if "fund_etf_spot_em" in source:
                item.underlying_endpoint = "Eastmoney ETF spot feed via AKShare"
            elif "stock_zh_index_daily" in source:
                item.underlying_endpoint = "Sina index feed via AKShare"
            else:
                item.underlying_endpoint = "Underlying AKShare endpoint not identified"
        elif source.startswith("tushare"):
            item.source_authority = "convenience_secondary"
            endpoint = item.source.split(".", 1)[1] if "." in item.source else "runtime status"
            item.underlying_endpoint = f"Tushare {endpoint}"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿"
    if abs_value >= 10_000:
        return f"{value / 10_000:.2f}万"
    return f"{value:.4g}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


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


def _add_gap(memo: ChinaResearchMemo, gap: str) -> None:
    if gap not in memo.evidence_gaps:
        memo.evidence_gaps.append(gap)


def parse_symbol_arg(raw: str) -> ChinaSymbolConfig:
    parts = raw.split(":")
    symbol = parts[0].strip()
    asset_type = parts[1].strip() if len(parts) >= 2 and parts[1].strip() else "etf"
    name = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else ""
    if not symbol:
        raise ValueError("empty symbol")
    return ChinaSymbolConfig(symbol=symbol, asset_type=asset_type, name=name)


def _akshare_etf_spot_row(symbol: str) -> tuple[pd.Series | None, str | None]:
    import akshare as ak

    df = ak.fund_etf_spot_em()
    if df is None or df.empty:
        return None, "AKShare fund_etf_spot_em returned no rows."
    match = df[df["代码"].astype(str) == symbol]
    if match.empty:
        return None, f"AKShare fund_etf_spot_em did not include ETF code {symbol}."
    return match.iloc[0], None


def fetch_akshare_etf_evidence(cfg: ChinaSymbolConfig) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        row, gap = _akshare_etf_spot_row(cfg.symbol)
        if gap:
            gaps.append(gap)
            return evidence, gaps
        assert row is not None
        data_date = _as_date_string(row.get("数据日期") or row.get("更新时间"))
        freshness = _freshness_from_date(data_date, stale_after_days=5)
        status = "ok" if freshness == "fresh" else "stale"
        name = str(row.get("名称") or cfg.name or cfg.symbol)
        price = _safe_float(row.get("最新价"))
        pct_change = _safe_float(row.get("涨跌幅"))
        amount = _safe_float(row.get("成交额"))
        total_mv = _safe_float(row.get("总市值"))
        discount = _safe_float(row.get("基金折价率"))

        evidence.extend([
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_price",
                claim=f"{name} latest ETF price from AKShare Eastmoney spot feed",
                value=_format_number(price),
                source="AKShare.fund_etf_spot_em",
                as_of_date=data_date,
                freshness=freshness,
                status=status,
                note="ETF spot feed; use as a China-market entry source, not final investment advice.",
            ),
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_price",
                claim="Latest ETF daily percentage change from AKShare spot feed",
                value=f"{pct_change:.2f}%" if pct_change is not None else "n/a",
                source="AKShare.fund_etf_spot_em",
                as_of_date=data_date,
                freshness=freshness,
                status="ok" if pct_change is not None and status == "ok" else "partial",
            ),
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_liquidity",
                claim="Latest ETF turnover amount from AKShare spot feed",
                value=_format_number(amount),
                source="AKShare.fund_etf_spot_em",
                as_of_date=data_date,
                freshness=freshness,
                status="ok" if amount is not None and status == "ok" else "partial",
            ),
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_etf_structure",
                claim="ETF discount/premium rate from AKShare spot feed",
                value=f"{discount:.2f}%" if discount is not None else "n/a",
                source="AKShare.fund_etf_spot_em",
                as_of_date=data_date,
                freshness=freshness,
                status="ok" if discount is not None and status == "ok" else "partial",
            ),
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_etf_structure",
                claim="ETF total market value from AKShare spot feed",
                value=_format_number(total_mv),
                source="AKShare.fund_etf_spot_em",
                as_of_date=data_date,
                freshness=freshness,
                status="ok" if total_mv is not None and status == "ok" else "partial",
            ),
        ])
    except Exception as exc:
        gaps.append(f"AKShare ETF spot adapter failed: {type(exc).__name__}: {exc}")
    return evidence, gaps


def _normalize_index_symbol(symbol: str) -> str:
    if symbol.startswith(("sh", "sz")):
        return symbol
    if symbol.endswith(".SH"):
        return "sh" + symbol.split(".")[0]
    if symbol.endswith(".SZ"):
        return "sz" + symbol.split(".")[0]
    if symbol.startswith("0") or symbol.startswith("9"):
        return "sh" + symbol
    return "sz" + symbol


def fetch_akshare_index_evidence(cfg: ChinaSymbolConfig) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        import akshare as ak

        normalized = _normalize_index_symbol(cfg.symbol)
        df = ak.stock_zh_index_daily(symbol=normalized)
        if df is None or df.empty:
            gaps.append(f"AKShare stock_zh_index_daily returned no rows for {normalized}.")
            return evidence, gaps
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        latest = df.sort_values("date").iloc[-1]
        latest_date = _as_date_string(latest.get("date"))
        freshness = _freshness_from_date(latest_date, stale_after_days=5)
        status = "ok" if freshness == "fresh" else "stale"
        close = _safe_float(latest.get("close"))
        volume = _safe_float(latest.get("volume"))
        trailing_return = None
        if len(df) > 240:
            first = _safe_float(df.sort_values("date").iloc[-241].get("close"))
            if first and close:
                trailing_return = close / first - 1.0

        evidence.extend([
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_index",
                claim=f"{cfg.name or cfg.symbol} latest index close from AKShare Sina index feed",
                value=_format_number(close),
                source="AKShare.stock_zh_index_daily",
                as_of_date=latest_date,
                freshness=freshness,
                status=status,
                note=f"normalized_symbol={normalized}",
            ),
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_index",
                claim="Approximate trailing 240-trading-day index return",
                value=_format_pct(trailing_return),
                source="AKShare.stock_zh_index_daily",
                as_of_date=latest_date,
                freshness=freshness,
                status="ok" if trailing_return is not None and status == "ok" else "partial",
            ),
            EvidenceItem(
                symbol=cfg.symbol,
                category="china_liquidity",
                claim="Latest index volume from AKShare index feed",
                value=_format_number(volume),
                source="AKShare.stock_zh_index_daily",
                as_of_date=latest_date,
                freshness=freshness,
                status="ok" if volume is not None and status == "ok" else "partial",
            ),
        ])
    except Exception as exc:
        gaps.append(f"AKShare index adapter failed: {type(exc).__name__}: {exc}")
    return evidence, gaps


def fetch_tushare_status_evidence(cfg: ChinaSymbolConfig) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    try:
        import tushare as ts

        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            evidence.append(EvidenceItem(
                symbol=cfg.symbol,
                category="china_data_source",
                claim="Tushare package is installed but TUSHARE_TOKEN is not configured",
                value="token_missing",
                source=f"tushare {getattr(ts, '__version__', 'unknown')}",
                as_of_date=datetime.now(timezone.utc).date().isoformat(),
                freshness="runtime_check",
                status="missing",
                note="Skeleton is ready; credentialed data fetch is intentionally blocked until token is configured.",
            ))
            gaps.append("TUSHARE_TOKEN is missing; Tushare credentialed data not fetched.")
            return evidence, gaps

        pro = ts.pro_api(token)
        end_date = datetime.now(timezone.utc).date().strftime("%Y%m%d")
        start_date = (datetime.now(timezone.utc).date() - timedelta(days=120)).strftime("%Y%m%d")
        ts_code = cfg.symbol
        if cfg.asset_type == "index" and "." not in ts_code:
            ts_code = f"{cfg.symbol}.SH" if cfg.symbol.startswith("0") else f"{cfg.symbol}.SZ"
        elif cfg.asset_type == "etf" and "." not in ts_code:
            ts_code = f"{cfg.symbol}.SH" if cfg.symbol.startswith("5") else f"{cfg.symbol}.SZ"

        endpoint = "index_daily" if cfg.asset_type == "index" else "fund_daily"
        df = getattr(pro, endpoint)(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            gaps.append(f"Tushare {endpoint} returned no rows for {ts_code}.")
            return evidence, gaps
        latest = df.sort_values("trade_date").iloc[-1]
        trade_date = _as_date_string(latest.get("trade_date"))
        close = _safe_float(latest.get("close"))
        pct_chg = _safe_float(latest.get("pct_chg"))
        freshness = _freshness_from_date(trade_date, stale_after_days=5)
        status = "ok" if freshness == "fresh" else "stale"
        evidence.append(EvidenceItem(
            symbol=cfg.symbol,
            category="china_tushare",
            claim=f"Latest close from Tushare {endpoint}",
            value=_format_number(close),
            source=f"Tushare.{endpoint}",
            as_of_date=trade_date,
            freshness=freshness,
            status=status,
            note=f"ts_code={ts_code}; pct_chg={pct_chg}",
        ))
    except Exception as exc:
        gaps.append(f"Tushare adapter failed: {type(exc).__name__}: {exc}")
    return evidence, gaps


def build_china_reconciliation_evidence(cfg: ChinaSymbolConfig, items: list[EvidenceItem]) -> tuple[list[EvidenceItem], list[str]]:
    evidence: list[EvidenceItem] = []
    gaps: list[str] = []
    runtime_date = datetime.now(timezone.utc).date().isoformat()

    akshare_item = next((item for item in items if item.source.startswith("AKShare") and item.category in {"china_price", "china_index"}), None)
    tushare_missing = next((item for item in items if item.source.lower().startswith("tushare") and item.value == "token_missing"), None)
    tushare_item = next((item for item in items if item.category == "china_tushare"), None)

    if tushare_missing is not None:
        evidence.append(EvidenceItem(
            symbol=cfg.symbol,
            category="china_reconciliation",
            claim="AKShare/Tushare field reconciliation status",
            value="blocked_by_tushare_token_missing",
            source="local DataOS reconciliation gate",
            as_of_date=runtime_date,
            freshness="runtime_check",
            status="missing",
            note="AKShare lane ran; Tushare comparison intentionally blocked until TUSHARE_TOKEN is configured.",
        ))
        return evidence, gaps

    if akshare_item is None and tushare_item is None:
        gaps.append("No AKShare or Tushare evidence available for reconciliation.")
        return evidence, gaps

    if akshare_item is None or tushare_item is None:
        evidence.append(EvidenceItem(
            symbol=cfg.symbol,
            category="china_reconciliation",
            claim="AKShare/Tushare field reconciliation status",
            value="one_source_missing",
            source="local DataOS reconciliation gate",
            as_of_date=runtime_date,
            freshness="runtime_check",
            status="partial",
            note=f"akshare_available={akshare_item is not None}; tushare_available={tushare_item is not None}",
        ))
        return evidence, gaps

    same_date = akshare_item.as_of_date == tushare_item.as_of_date
    sources_ok = akshare_item.status == "ok" and tushare_item.status == "ok"
    evidence.append(EvidenceItem(
        symbol=cfg.symbol,
        category="china_reconciliation",
        claim="AKShare/Tushare date reconciliation status",
        value="same_trade_date" if same_date else "date_mismatch",
        source="local DataOS reconciliation gate",
        as_of_date=runtime_date,
        freshness="runtime_check",
        status="ok" if same_date and sources_ok else "partial",
        note=f"akshare_date={akshare_item.as_of_date}; tushare_date={tushare_item.as_of_date}; akshare_status={akshare_item.status}; tushare_status={tushare_item.status}; akshare_value={akshare_item.value}; tushare_value={tushare_item.value}",
    ))
    return evidence, gaps


def build_china_memo(cfg: ChinaSymbolConfig, generated_at: datetime | None = None) -> ChinaResearchMemo:
    generated_at = generated_at or datetime.now(timezone.utc)
    memo = ChinaResearchMemo(
        symbol=cfg.symbol,
        asset_type=cfg.asset_type,
        name=cfg.name,
        generated_at=generated_at.isoformat(),
    )

    if cfg.asset_type == "index":
        evidence, gaps = fetch_akshare_index_evidence(cfg)
    else:
        evidence, gaps = fetch_akshare_etf_evidence(cfg)
    classify_convenience_evidence(evidence)
    memo.evidence.extend(evidence)
    for gap in gaps:
        _add_gap(memo, gap)

    tushare_evidence, tushare_gaps = fetch_tushare_status_evidence(cfg)
    classify_convenience_evidence(tushare_evidence)
    memo.evidence.extend(tushare_evidence)
    for gap in tushare_gaps:
        _add_gap(memo, gap)

    reconciliation_evidence, reconciliation_gaps = build_china_reconciliation_evidence(cfg, memo.evidence)
    memo.evidence.extend(reconciliation_evidence)
    for gap in reconciliation_gaps:
        _add_gap(memo, gap)

    memo.research_suggestions = [
        sanitize_suggestion("建议核对 AKShare 与 Tushare 的同字段口径：价格、成交额、复权、交易日是否一致。"),
        sanitize_suggestion("建议补充基金/指数成分、行业权重、跟踪误差和资金流数据，再进入深度研究。"),
        sanitize_suggestion("建议记录数据缺口和源站异常，不让 LLM 代替数据源补全事实。"),
        sanitize_suggestion("建议把该标的接入组合风险复核：市场暴露、币种暴露、相关性和回撤。"),
    ]
    if not memo.evidence:
        _add_gap(memo, "No China-market evidence was collected; do not use this memo externally.")
    return memo


def flatten_evidence(memos: list[ChinaResearchMemo]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for memo in memos:
        items.extend(memo.evidence)
    return items


def render_china_memo(memos: list[ChinaResearchMemo], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    items = flatten_evidence(memos)
    ok_count = sum(1 for item in items if item.status == "ok")
    issue_count = sum(1 for item in items if item.status != "ok") + sum(len(m.evidence_gaps) for m in memos)

    lines: list[str] = []
    lines.append("# Spike 2 China Data Memo — AKShare / Tushare Skeleton")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("")
    lines.append("- Goal: put China-market data into the same Data Quality Gate and Evidence Ledger.")
    lines.append("- Convenience/secondary adapter: AKShare, with the underlying endpoint retained where known.")
    lines.append("- Credentialed convenience adapter: Tushare, gated by `TUSHARE_TOKEN`.")
    lines.append("- Official-source coverage is incomplete; PBOC, NBS, CNINFO, SSE, SZSE and HKEX remain explicit source targets until fetched evidence exists.")
    lines.append("- Decision boundary: research memo only; no trade decision, no position sizing, no execution.")
    lines.append("")
    lines.append("## 2. Data Quality Summary")
    lines.append("")
    lines.append(f"- Symbols: {len(memos)}")
    lines.append(f"- Evidence items: {len(items)}")
    lines.append(f"- OK items: {ok_count}")
    lines.append(f"- Items/gaps needing review: {issue_count}")
    lines.append("")

    for memo in memos:
        title = f"{memo.symbol} {memo.name}".strip()
        lines.append(f"## 3. {title} China Data Card")
        lines.append("")
        lines.append(f"- Asset type: `{memo.asset_type}`")
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
                f"| {item.category} | {item.claim.replace('|', '/')} | {item.value.replace('|', '/')} | {item.source.replace('|', '/')} | {item.as_of_date} | {item.freshness} | {item.status} |"
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

    lines.append("## 4. Integration Verdict")
    lines.append("")
    lines.append("- AKShare can enter the China-market branch only as a convenience/secondary market-data adapter, not official first-party evidence.")
    lines.append("- Tushare is wired as a credential-gated supplement; without token it must show as missing, not silently disappear.")
    lines.append("- China-market fields now use the same source/as_of_date/freshness/status contract as the US filing-backed memo.")
    lines.append("")
    lines.append("## 5. Decision Boundary")
    lines.append("")
    lines.append("本报告不输出买入、卖出、持有或仓位建议。任何交易决策应由使用者自行完成。")
    lines.append("")
    return "\n".join(lines)


def run(configs: list[ChinaSymbolConfig], out_dir: Path) -> Spike2RunResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    memos = [build_china_memo(cfg, generated_at=generated_at) for cfg in configs]
    report_path = out_dir / "china_data_memo.md"
    ledger_csv_path = out_dir / "china_evidence_ledger.csv"
    ledger_json_path = out_dir / "china_evidence_ledger.json"
    write_ledger(flatten_evidence(memos), ledger_csv_path, ledger_json_path)
    ledger_json_path.write_text(json.dumps([asdict(item) for item in flatten_evidence(memos)], ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_china_memo(memos, generated_at=generated_at), encoding="utf-8")
    return Spike2RunResult(report_path=report_path, ledger_csv_path=ledger_csv_path, ledger_json_path=ledger_json_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Spike 2 China-market data memo pipeline.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["510300:etf:沪深300ETF", "000300:index:沪深300指数"],
        help="China symbols as code[:asset_type[:name]], e.g. 510300:etf:沪深300ETF 000300:index:沪深300指数",
    )
    parser.add_argument("--out", type=Path, default=Path("reports/spike-2"))
    args = parser.parse_args(argv)
    configs = [parse_symbol_arg(raw) for raw in args.symbols]
    result = run(configs, args.out)
    print(f"report={result.report_path}")
    print(f"ledger_csv={result.ledger_csv_path}")
    print(f"ledger_json={result.ledger_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
