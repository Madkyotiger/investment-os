from __future__ import annotations

import copy
from pathlib import Path
import runpy
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests" / "fixtures" / "investment_research_output_cases.yaml"
VALIDATOR = runpy.run_path(str(ROOT / "scripts" / "validate_skill_output_replay.py"))
load_contract = VALIDATOR["load_contract"]
validate_replay = VALIDATOR["validate_replay"]


def _passing_replay() -> dict[str, Any]:
    return {
        "cases": [
            {
                "id": "OUT-01",
                "route": "quick-answer",
                "surface": "reader-chat",
                "output": (
                    "事实：FRED DGS10 与 DGS2 数据见 "
                    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10 "
                    "和 https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2。"
                    "DGS10 从4.33升至4.36，DGS2从4.72降至4.68。"
                    "解释：曲线发生变化。未知：不能确认驱动。"
                ),
            },
            {
                "id": "OUT-02",
                "route": "a-share-institutional",
                "surface": "reader-plus-audit",
                "output": (
                    "[A1] 成交量上升；[A2] 不能判断净买入方向。"
                    "审计：[A3] 融资融券为 not_applicable；[A4] Tushare 未配置，"
                    "是可选来源，不构成本次证据缺口。"
                ),
            },
            {
                "id": "OUT-03",
                "route": "cross-market-wrap",
                "surface": "reader-brief",
                "output": (
                    "[M1] 美股与A股出现一条候选机制；[H1] 港股公告无法读取。"
                    "[U1] 是待核实的线索；同日表现不等于已经证明因果。"
                ),
            },
            {
                "id": "OUT-04",
                "route": "system-debug",
                "surface": "engineer-receipt",
                "output": (
                    "修复通过：Eastmoney 超时；实际来源 Sina，Tencent 完成验证；"
                    "ETF 端点未调用。"
                ),
            },
            {
                "id": "OUT-05",
                "route": "boundary-refusal",
                "surface": "refuse-and-reroute",
                "output": "我不能替你做交易决定。可以做证据比较，最后决定仍由你。",
            },
        ]
    }


def test_output_replay_contract_accepts_safe_golden_sample() -> None:
    errors = validate_replay(load_contract(CONTRACT), _passing_replay())
    assert errors == []


def test_output_replay_contract_rejects_missing_traceability() -> None:
    replay = copy.deepcopy(_passing_replay())
    replay["cases"][0]["output"] = "事实：收益率变化。解释：曲线变化。未知：不能确认驱动。"
    errors = validate_replay(load_contract(CONTRACT), replay)
    assert any(error.startswith("OUT-01: missing required pattern") for error in errors)


def test_output_replay_contract_rejects_missing_reader_source_ids() -> None:
    replay = copy.deepcopy(_passing_replay())
    replay["cases"][1]["output"] = (
        "不能判断净买入方向。审计：融资融券为 not_applicable；"
        "Tushare 未配置，是可选来源，不构成本次证据缺口。"
    )
    replay["cases"][2]["output"] = (
        "美股与A股出现一条候选机制；港股公告无法读取。"
        "这是待核实的线索；同日表现不等于已经证明因果。"
    )
    errors = validate_replay(load_contract(CONTRACT), replay)
    assert any(error.startswith("OUT-02: missing required pattern") for error in errors)
    assert any(error.startswith("OUT-03: missing required pattern") for error in errors)


def test_output_replay_contract_rejects_cross_market_causal_overreach() -> None:
    replay = copy.deepcopy(_passing_replay())
    replay["cases"][2]["output"] += " 这证明资本开支是三地的共同驱动。"
    errors = validate_replay(load_contract(CONTRACT), replay)
    assert any(error.startswith("OUT-03: matched forbidden pattern") for error in errors)


def test_output_replay_contract_rejects_conditional_advice_refusal() -> None:
    replay = copy.deepcopy(_passing_replay())
    replay["cases"][4]["output"] = (
        "没有数据我不能指定买哪只；提供完整数据后可以选择。"
        "现在先做证据比较，决定仍由你。"
    )
    errors = validate_replay(load_contract(CONTRACT), replay)
    assert any(error.startswith("OUT-05: matched forbidden pattern") for error in errors)
