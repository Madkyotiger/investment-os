from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .cxo_intelligence import CXOProfile, build_cxo_brief_items, write_cxo_outputs
from .pipeline import SymbolConfig, analyze_history, metrics_to_csv, render_report, run as run_pipeline
from .source_universe_intake import SourceCandidate


def _synthetic_history(start: float, drift: float, wobble: float) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-06-30", periods=100)
    steps = np.arange(len(dates), dtype=float)
    close = start + drift * steps + wobble * np.sin(steps / 6.0)
    return pd.DataFrame({"Close": close}, index=dates)


def _demo_candidates() -> list[SourceCandidate]:
    return [
        SourceCandidate(
            item_id="demo:company:margin-quality",
            lane="company_events",
            title="示例财报正文改变了利润率问题",
            summary="示例公司披露显示收入增长，但利润率变化仍需拆分业务组合与一次性因素。",
            source="synthetic demo fixture",
            source_type="demo_source_body",
            as_of_date="2026-06-30",
            themes="AI,margin,earnings",
            source_authority=4,
            freshness=5,
            evidence_change=4,
            magnitude=3,
            novelty=3,
            decision_usefulness=5,
            portfolio_relevance=3,
            confidence="synthetic_verified",
            next_check="下一份财报正文与业绩会记录",
            kill_signal="后续披露不能确认利润率变化，或变化完全来自一次性因素",
            cannot_prove="单期示例数据不能证明长期趋势。",
            thesis_key="demo:company:margin-quality",
            research_question="利润率变化是否足以调整研究优先级？",
            thesis_impact="unknown",
            counter_explanation="变化可能来自短期业务组合，而不是结构性改善。",
            next_primary_source="下一份财报正文与业绩会记录",
            evidence_status="demo_fixture",
            geography="US",
        ),
        SourceCandidate(
            item_id="demo:macro:rates",
            lane="macro_regime",
            title="示例利率曲线变化需要进入判断底图",
            summary="示例数据中的长短端利率同时变化，先把它当作融资成本背景，不把它直接解释成股市方向。",
            source="synthetic demo fixture",
            source_type="demo_macro_data",
            as_of_date="2026-06-30",
            themes="Fed,rates",
            source_authority=4,
            freshness=5,
            evidence_change=3,
            magnitude=3,
            novelty=2,
            decision_usefulness=4,
            portfolio_relevance=2,
            confidence="synthetic_verified",
            next_check="官方利率数据与行业相对强弱",
            kill_signal="官方数据没有确认变化，或市场代理资产不配合",
            cannot_prove="利率变化本身不能证明股市方向。",
            thesis_key="demo:macro:rates",
            research_question="利率变化正在改变融资成本，还是只构成短期背景？",
            thesis_impact="unknown",
            counter_explanation="期限溢价变化可能比政策预期更重要。",
            next_primary_source="官方利率数据与市场代理资产",
            evidence_status="demo_fixture",
            geography="US",
        ),
    ]


def run_demo(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    configs = [
        SymbolConfig(symbol="DEMO_US", name="Synthetic US Equity", market="US", asset_class="equity", source="fixture"),
        SymbolConfig(symbol="DEMO_CN", name="Synthetic China Equity", market="CN", asset_class="equity", source="fixture"),
    ]
    histories = [
        _synthetic_history(100.0, 0.18, 1.4),
        _synthetic_history(100.0, -0.05, 1.0),
    ]
    metrics = [analyze_history(cfg, history, generated_at=generated_at) for cfg, history in zip(configs, histories)]
    metrics_path = out_dir / "market-metrics.csv"
    report_path = out_dir / "market-report.md"
    metrics_to_csv(metrics, metrics_path)
    report_path.write_text(
        render_report(
            {"profile_name": "offline-demo", "report_title": "Investment OS offline demo"},
            metrics,
            generated_at=generated_at,
        ),
        encoding="utf-8",
    )

    profile = CXOProfile(
        profile_id="demo_reader",
        label="Demo reader",
        role="个人投资者",
        decision_horizon="days to quarters",
        business_exposure=["personal investment research"],
        asset_exposure=["US and China market context"],
        current_projects=["investment research system"],
        trusted_source_preference=["primary source"],
        brief_style="concise Chinese research brief",
        avoid=["trade instructions"],
        relevance_keywords=["AI", "margin", "earnings", "Fed", "rates"],
    )
    candidates = _demo_candidates()
    items = build_cxo_brief_items(candidates, profile, max_items=5)
    brief_path, ranked_path, quality_path = write_cxo_outputs(
        items,
        profile,
        out_dir,
        generated_at=generated_at,
        candidates=candidates,
    )
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if any(quality.values()):
        print(f"quality_scan=fail details={quality}", file=sys.stderr)
        return 3
    expected = [metrics_path, report_path, brief_path, ranked_path, quality_path]
    missing = [str(path) for path in expected if not path.exists()]
    if missing:
        print(f"demo=fail missing={missing}", file=sys.stderr)
        return 4
    print("demo=pass")
    print("quality_scan=pass")
    for path in expected:
        print(f"artifact={path}")
    return 0


def run_doctor() -> int:
    core = {name: importlib.util.find_spec(name) is not None for name in ("numpy", "pandas", "yaml")}
    optional = {
        name: importlib.util.find_spec(name) is not None
        for name in ("yfinance", "openbb", "financetoolkit", "edgar", "akshare", "tushare")
    }
    supported = (3, 11) <= sys.version_info[:2] < (3, 13)
    result = {
        "investment_os": __version__,
        "python": platform.python_version(),
        "python_supported": supported,
        "core": core,
        "optional": optional,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if supported and all(core.values()) else 1


def run_live(config: Path, out_dir: Path, strict: bool) -> int:
    report_path, metrics_path = run_pipeline(config, out_dir)
    frame = pd.read_csv(metrics_path)
    usable = int((frame.get("data_quality") == "ok").sum()) if not frame.empty and "data_quality" in frame else 0
    print(f"report={report_path}")
    print(f"metrics={metrics_path}")
    print(f"usable_rows={usable}")
    if strict and usable == 0:
        print("live_run=fail reason=no_usable_rows", file=sys.stderr)
        return 2
    print("live_run=pass" if usable else "live_run=degraded")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="investment-os", description="Evidence-first personal investment research tools.")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check the local Python environment and optional connectors.")

    demo = subparsers.add_parser("demo", help="Run the deterministic offline evaluation.")
    demo.add_argument("--out", type=Path, default=Path("demo-output"))

    live = subparsers.add_parser("run", help="Run a watchlist through the live market-price path.")
    live.add_argument("--config", type=Path, required=True)
    live.add_argument("--out", type=Path, required=True)
    live.add_argument("--strict", action="store_true", help="Exit 2 if no symbol has usable data.")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return run_doctor()
    if args.command == "demo":
        return run_demo(args.out)
    if args.command == "run":
        return run_live(args.config, args.out, args.strict)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
