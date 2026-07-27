from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

FORBIDDEN_DECISION_WORDS = (
    "买入", "卖出", "持有", "加仓", "减仓", "满仓", "清仓", "仓位",
    "buy", "sell", "hold", "overweight", "underweight",
    "position", "position sizing", "position size", "execute", "execution", "trade", "trading",
)

DISCLAIMER = (
    "本报告只用于信息整理、研究讨论和风险提示，不构成投资建议、交易建议或收益承诺。"
    "市场有风险，任何交易决策应由使用者自行完成并自行承担。"
)


@dataclass
class SymbolConfig:
    symbol: str
    name: str = ""
    market: str = ""
    asset_class: str = ""
    source: str = "yahoo"
    notes: str = ""


@dataclass
class SymbolMetrics:
    symbol: str
    name: str
    market: str
    asset_class: str
    source: str
    latest_date: str
    latest_price: float | None
    return_5d: float | None
    return_20d: float | None
    return_60d: float | None
    volatility_20d_ann: float | None
    max_drawdown_1y: float | None
    ma20: float | None
    ma60: float | None
    trend_state: str
    data_quality: str
    research_priority: str
    evidence_gaps: str
    research_suggestion: str


def pct(value: float | None) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "n/a"
    return f"{value * 100:.2f}%"


def money(value: float | None) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "n/a"
    return f"{value:.2f}"


def safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def load_watchlist(path: Path) -> tuple[dict[str, Any], list[SymbolConfig]]:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    symbols = [SymbolConfig(**item) for item in config.get("symbols", [])]
    if not symbols:
        raise ValueError(f"No symbols found in {path}")
    return config, symbols


def fetch_yahoo_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not installed")
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, auto_adjust=True)
    if hist is None or hist.empty:
        return pd.DataFrame()
    hist = hist.copy()
    hist.index = pd.to_datetime(hist.index)
    return hist


def max_drawdown(close: pd.Series) -> float | None:
    close = close.dropna()
    if close.empty:
        return None
    cumulative_max = close.cummax()
    drawdowns = close / cumulative_max - 1.0
    return safe_float(drawdowns.min())


def calc_return(close: pd.Series, days: int) -> float | None:
    close = close.dropna()
    if len(close) <= days:
        return None
    start = close.iloc[-days - 1]
    end = close.iloc[-1]
    if start == 0 or pd.isna(start) or pd.isna(end):
        return None
    return safe_float(end / start - 1.0)


def calc_volatility(close: pd.Series, days: int = 20) -> float | None:
    close = close.dropna()
    if len(close) <= days:
        return None
    returns = close.pct_change().dropna().tail(days)
    if returns.empty:
        return None
    return safe_float(returns.std() * np.sqrt(252))


def trend_state(latest: float | None, ma20: float | None, ma60: float | None) -> str:
    if latest is None or ma20 is None or ma60 is None:
        return "insufficient_data"
    if latest > ma20 > ma60:
        return "price_above_short_and_mid_ma"
    if latest < ma20 < ma60:
        return "price_below_short_and_mid_ma"
    return "mixed_or_transition"


def classify_priority(data_quality: str, ret20: float | None, vol20: float | None, dd: float | None, trend: str) -> tuple[str, str]:
    """Return research priority and research-only suggestion.

    The wording is intentionally about research actions, not trading decisions.
    """
    if data_quality != "ok":
        return (
            "data_check_first",
            "建议先补充替代数据源并核验最新价格/成交量；数据未过关前不升级研究优先级。",
        )

    risk_flags: list[str] = []
    if dd is not None and dd < -0.25:
        risk_flags.append("1年回撤较深")
    if vol20 is not None and vol20 > 0.45:
        risk_flags.append("近期波动偏高")

    if risk_flags:
        return (
            "risk_review",
            "建议进入风险复核清单：补充基本面、事件、流动性和同业对比，先解释风险来源。",
        )

    if ret20 is not None and ret20 > 0.08 and trend == "price_above_short_and_mid_ma":
        return (
            "priority_research",
            "建议进入重点研究清单：补估值、业绩驱动、催化因素和反方 thesis，形成一页研究卡。",
        )

    if ret20 is not None and ret20 < -0.08 and trend == "price_below_short_and_mid_ma":
        return (
            "watch_with_triggers",
            "建议保持观察并设置复盘触发条件：价格企稳、成交改善、基本面或政策事件更新。",
        )

    return (
        "standard_monitoring",
        "建议纳入标准观察：每周更新价格、波动、回撤和关键新闻，等待更清晰证据。",
    )


def sanitize_suggestion(text: str) -> str:
    lowered = text.lower()
    bad = [word for word in FORBIDDEN_DECISION_WORDS if word.lower() in lowered]
    if bad:
        raise ValueError(f"Suggestion contains decision wording: {bad}: {text}")
    return text


def analyze_history(cfg: SymbolConfig, hist: pd.DataFrame, generated_at: datetime | None = None) -> SymbolMetrics:
    generated_at = generated_at or datetime.now(timezone.utc)
    if hist is None or hist.empty or "Close" not in hist.columns:
        priority, suggestion = classify_priority("missing", None, None, None, "insufficient_data")
        return SymbolMetrics(
            symbol=cfg.symbol,
            name=cfg.name,
            market=cfg.market,
            asset_class=cfg.asset_class,
            source=cfg.source,
            latest_date="n/a",
            latest_price=None,
            return_5d=None,
            return_20d=None,
            return_60d=None,
            volatility_20d_ann=None,
            max_drawdown_1y=None,
            ma20=None,
            ma60=None,
            trend_state="insufficient_data",
            data_quality="missing",
            research_priority=priority,
            evidence_gaps="No price history returned from configured source.",
            research_suggestion=sanitize_suggestion(suggestion),
        )

    close = hist["Close"].dropna()
    if close.empty:
        return analyze_history(cfg, pd.DataFrame(), generated_at)

    latest_date = close.index[-1]
    latest_price = safe_float(close.iloc[-1])
    ret5 = calc_return(close, 5)
    ret20 = calc_return(close, 20)
    ret60 = calc_return(close, 60)
    vol20 = calc_volatility(close, 20)
    dd = max_drawdown(close)
    ma20 = safe_float(close.tail(20).mean()) if len(close) >= 20 else None
    ma60 = safe_float(close.tail(60).mean()) if len(close) >= 60 else None
    trend = trend_state(latest_price, ma20, ma60)

    age_days = (generated_at.date() - latest_date.date()).days
    if len(close) < 60:
        quality = "insufficient"
        gaps = "Less than 60 observations; trend and risk metrics are weak."
    elif age_days > 7:
        quality = "stale"
        gaps = f"Latest price date is {age_days} calendar days old; verify source freshness."
    else:
        quality = "ok"
        gaps = "Fundamentals/news/valuation are not included in Phase 1 output."

    priority, suggestion = classify_priority(quality, ret20, vol20, dd, trend)

    return SymbolMetrics(
        symbol=cfg.symbol,
        name=cfg.name,
        market=cfg.market,
        asset_class=cfg.asset_class,
        source=cfg.source,
        latest_date=latest_date.strftime("%Y-%m-%d"),
        latest_price=latest_price,
        return_5d=ret5,
        return_20d=ret20,
        return_60d=ret60,
        volatility_20d_ann=vol20,
        max_drawdown_1y=dd,
        ma20=ma20,
        ma60=ma60,
        trend_state=trend,
        data_quality=quality,
        research_priority=priority,
        evidence_gaps=gaps,
        research_suggestion=sanitize_suggestion(suggestion),
    )


def collect_metrics(symbols: Iterable[SymbolConfig]) -> list[SymbolMetrics]:
    metrics: list[SymbolMetrics] = []
    for cfg in symbols:
        if cfg.source != "yahoo":
            hist = pd.DataFrame()
        else:
            try:
                hist = fetch_yahoo_history(cfg.symbol)
            except Exception:
                hist = pd.DataFrame()
        metrics.append(analyze_history(cfg, hist))
    return metrics


def metrics_to_csv(metrics: list[SymbolMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(metrics[0]).keys()) if metrics else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in metrics:
            writer.writerow(asdict(item))


def render_report(config: dict[str, Any], metrics: list[SymbolMetrics], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    ok_count = sum(1 for m in metrics if m.data_quality == "ok")
    lines: list[str] = []
    lines.append(f"# {config.get('report_title', 'Investment Research Information Report')}")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("")
    lines.append(f"- Profile: `{config.get('profile_name', 'unnamed')}`")
    lines.append(f"- Symbols: {len(metrics)}")
    lines.append(f"- Data quality OK: {ok_count}/{len(metrics)}")
    lines.append("- Decision boundary: research suggestions only; no trade decision.")
    lines.append("")
    lines.append("## 2. Market Snapshot")
    lines.append("")
    lines.append("| Symbol | Name | Market | Latest | 5D | 20D | 60D | 20D Vol Ann. | Max DD 1Y | Data | Priority |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for m in metrics:
        lines.append(
            f"| `{m.symbol}` | {m.name} | {m.market} | {money(m.latest_price)} | {pct(m.return_5d)} | {pct(m.return_20d)} | {pct(m.return_60d)} | {pct(m.volatility_20d_ann)} | {pct(m.max_drawdown_1y)} | {m.data_quality} | {m.research_priority} |"
        )
    lines.append("")
    lines.append("## 3. Research Suggestions")
    lines.append("")
    for m in metrics:
        lines.append(f"### {m.symbol} — {m.name}")
        lines.append("")
        lines.append(f"- Trend state: `{m.trend_state}`")
        lines.append(f"- Evidence gaps: {m.evidence_gaps}")
        lines.append(f"- Research suggestion: {m.research_suggestion}")
        lines.append("")
    lines.append("## 4. Next Data Work")
    lines.append("")
    lines.append("- 接入 AKShare/Tushare，用于 A股/中国宏观/行业字段校验。")
    lines.append("- 接入 holdings.csv，把单标的观察升级为组合风险观察。")
    lines.append("- 对重点标的追加财务、新闻、公告和估值数据。")
    lines.append("- 每份外发报告先做隐私和决策边界检查。")
    lines.append("")
    lines.append("## 5. Decision Boundary")
    lines.append("")
    lines.append("本报告不输出买入、卖出、持有或仓位建议。任何交易决策应由使用者自行完成。")
    lines.append("")
    return "\n".join(lines)


def run(config_path: Path, out_dir: Path) -> tuple[Path, Path]:
    config, symbols = load_watchlist(config_path)
    metrics = collect_metrics(symbols)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "metrics.csv"
    report_path = out_dir / "report.md"
    metrics_to_csv(metrics, metrics_path)
    report = render_report(config, metrics)
    report_path.write_text(report, encoding="utf-8")
    return report_path, metrics_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run information-first investment research pipeline.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report_path, metrics_path = run(args.config, args.out)
    print(f"report={report_path}")
    print(f"metrics={metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
