from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .cxo_intelligence import CXOProfile, build_cxo_brief_items, write_cxo_outputs
from .daily_runner import DailyRunError, run_daily
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
            retrieved_at="2026-07-01T00:00:00+00:00",
            freshness_status="current",
            freshness_threshold_days=3,
            source_url="https://example.invalid/demo-company-source",
            content_hash="sha256:demo-company-margin-quality",
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
            retrieved_at="2026-07-01T00:00:00+00:00",
            freshness_status="current",
            freshness_threshold_days=3,
            source_url="https://example.invalid/demo-macro-source",
            content_hash="sha256:demo-macro-rates",
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


OPTIONAL_PACKAGE_USAGE = {
    "yfinance": ["run", "daily"],
    "openbb": ["optional_global_research_spike"],
    "financetoolkit": ["optional_global_research_spike"],
    "edgar": ["optional_complex_filing_research"],
    "akshare": ["a-share-daily", "optional_china_research"],
    "tushare": ["optional_china_second_source"],
}


def _probe_daily_connectors() -> dict[str, str]:
    from .hard_source_collectors import (
        _download_stooq_snapshot,
        _download_yfinance_snapshot,
        _fred_latest,
        _safe_sec_recent,
    )

    def probe(callback) -> str:
        try:
            return "available" if callback() else "unavailable"
        except Exception:
            return "unavailable"

    statuses = {
        "yfinance": probe(lambda: bool(_download_yfinance_snapshot(["SPY"]))),
        "fred": probe(lambda: _fred_latest("DGS10") is not None),
        "stooq": probe(lambda: bool(_download_stooq_snapshot(["SPY"]))),
    }
    statuses["sec"] = (
        probe(lambda: bool(_safe_sec_recent()))
        if os.getenv("SEC_EDGAR_IDENTITY", "").strip()
        else "blocked_missing_identity"
    )
    return statuses


def _probe_china_keyless_connector() -> str:
    try:
        import akshare as ak

        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=14)
        frame = ak.stock_zh_a_daily(
            symbol="sh601318",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="",
        )
        return "available" if frame is not None and not frame.empty else "unavailable"
    except Exception:
        return "unavailable"


def run_doctor(probe_target: str | None = None) -> int:
    core = {name: importlib.util.find_spec(name) is not None for name in ("numpy", "pandas", "yaml")}
    optional_packages = {
        name: {
            "importable": importlib.util.find_spec(name) is not None,
            "used_by": used_by,
        }
        for name, used_by in OPTIONAL_PACKAGE_USAGE.items()
    }
    supported = (3, 11) <= sys.version_info[:2] < (3, 13)
    sec_configured = bool(os.getenv("SEC_EDGAR_IDENTITY", "").strip())
    connectors = {
        "yfinance": {
            "adapter_installed": optional_packages["yfinance"]["importable"],
            "configured": optional_packages["yfinance"]["importable"],
            "required_for_daily": True,
            "used_by": ["run", "daily"],
            "live_probe": "not_run",
        },
        "sec": {
            "adapter_installed": True,
            "configured": sec_configured,
            "required_for_daily": True,
            "used_by": ["daily"],
            "live_probe": "not_run",
        },
        "fred": {
            "adapter_installed": True,
            "configured": True,
            "required_for_daily": True,
            "used_by": ["daily"],
            "live_probe": "not_run",
        },
        "stooq": {
            "adapter_installed": True,
            "configured": True,
            "required_for_daily": False,
            "used_by": ["daily_cross_check"],
            "live_probe": "not_run",
        },
        "akshare": {
            "adapter_installed": optional_packages["akshare"]["importable"],
            "configured": optional_packages["akshare"]["importable"],
            "required_for_china_keyless": True,
            "used_by": ["a-share-daily"],
            "live_probe": "not_run",
        },
        "tushare": {
            "adapter_installed": optional_packages["tushare"]["importable"],
            "configured": bool(os.getenv("TUSHARE_TOKEN", "").strip()),
            "required_for_china_keyless": False,
            "used_by": ["optional_china_second_source"],
            "live_probe": "not_run",
        },
    }
    if probe_target == "daily":
        probe_results = _probe_daily_connectors()
        for name, status in probe_results.items():
            connectors[name]["live_probe"] = status
        required_ready = all(
            connectors[name]["live_probe"] == "available"
            for name in ("yfinance", "sec", "fred")
        )
        if not required_ready:
            daily_readiness = "degraded"
        elif connectors["stooq"]["live_probe"] == "available":
            daily_readiness = "ready"
        else:
            daily_readiness = "ready_with_degraded_cross_check"
    else:
        daily_readiness = (
            "configured"
            if optional_packages["yfinance"]["importable"] and sec_configured
            else "degraded"
        )

    if probe_target == "china-keyless":
        connectors["akshare"]["live_probe"] = _probe_china_keyless_connector()
        china_keyless_readiness = (
            "ready" if connectors["akshare"]["live_probe"] == "available" else "degraded"
        )
    else:
        china_keyless_readiness = (
            "configured" if optional_packages["akshare"]["importable"] else "degraded"
        )
    result = {
        "investment_os": __version__,
        "python": platform.python_version(),
        "python_supported": supported,
        "core": core,
        "optional_packages": optional_packages,
        "connectors": connectors,
        "daily_readiness": daily_readiness,
        "china_keyless_readiness": china_keyless_readiness,
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

    doctor = subparsers.add_parser(
        "doctor",
        help="Separate package importability, connector configuration, and optional live health.",
    )
    doctor.add_argument(
        "--probe",
        choices=("daily", "china-keyless"),
        help="Run live health probes for the selected connector set.",
    )

    demo = subparsers.add_parser("demo", help="Run the deterministic offline evaluation.")
    demo.add_argument("--out", type=Path, default=Path("demo-output"))

    live = subparsers.add_parser("run", help="Run a watchlist through the live market-price path.")
    live.add_argument("--config", type=Path, required=True)
    live.add_argument("--out", type=Path, required=True)
    live.add_argument("--strict", action="store_true", help="Exit 2 if no symbol has usable data.")

    daily = subparsers.add_parser("daily", help="Collect, validate, update state, and write a local daily brief.")
    daily.add_argument("--config", type=Path, required=True, help="Watchlist YAML path.")
    daily.add_argument("--profile", type=Path, required=True, help="Reader profile YAML path.")
    daily.add_argument("--state", type=Path, required=True, help="Durable topic-state JSON path.")
    daily.add_argument("--out", type=Path, required=True)
    daily.add_argument("--strict", action="store_true", help="In live mode, fail if every usable source fails.")
    daily.add_argument("--offline", action="store_true", help="Use the deterministic bundled synthetic fixture.")

    a_share = subparsers.add_parser(
        "a-share-daily",
        help="Build a keyless A-share institutional-observation brief plus auditable evidence.",
    )
    a_share.add_argument("--config", type=Path, required=True, help="A-share watchlist YAML path.")
    a_share.add_argument("--out", type=Path, required=True)
    a_share.add_argument("--strict", action="store_true", help="Exit 2 if no symbol has a fresh usable price row.")
    a_share.add_argument("--offline", action="store_true", help="Use the deterministic bundled synthetic fixture.")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return run_doctor(args.probe)
    if args.command == "demo":
        return run_demo(args.out)
    if args.command == "run":
        return run_live(args.config, args.out, args.strict)
    if args.command == "daily":
        try:
            result = run_daily(
                args.config,
                args.profile,
                args.state,
                args.out,
                strict=args.strict,
                offline=args.offline,
            )
        except DailyRunError as error:
            print(f"daily_run=fail reason={error}", file=sys.stderr)
            return 2
        print(f"daily_run={result.status}")
        print(f"brief={result.brief_path}")
        print(f"manifest={result.manifest_path}")
        return 0
    if args.command == "a-share-daily":
        from .a_share_daily import run_a_share_daily

        result = run_a_share_daily(args.config, args.out, offline=args.offline)
        if args.strict and result.usable_symbols == 0:
            print("a_share_daily=fail reason=no_usable_rows", file=sys.stderr)
            return 2
        print(
            f"a_share_daily=completed usable_symbols={result.usable_symbols} "
            f"brief={result.brief_path} receipt={result.receipt_path}"
        )
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
