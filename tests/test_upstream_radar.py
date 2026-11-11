from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from investment_os.upstream_radar import (
    evaluate_packet,
    load_objective,
    render_reader_brief,
    write_outputs,
)
from investment_os.upstream_radar_preflight import build_preflight, required_coverage_checks

CONFIG = Path("configs/upstream_radar.sample.yaml")
AS_OF = datetime.fromisoformat("2026-09-04T13:33:00+08:00")
CHECKS = (
    ("macro_upstream", "policy_rates_liquidity"),
    ("macro_upstream", "inflation_growth_labor"),
    ("macro_upstream", "energy_geopolitics"),
    ("ai_upstream", "ai_demand_capex"),
    ("ai_upstream", "semiconductors_network_memory"),
    ("ai_upstream", "power_grid_cooling_datacenters"),
    ("company_events", "leader_earnings_guidance_material_events"),
    ("market_interpretation", "financial_media_expert_views"),
)


def _write_source(run_dir: Path, source_id: str, body: str = "verified coverage body") -> dict:
    rel = f"evidence/{source_id}.txt"
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return {
        "source_id": source_id,
        "url": f"https://example.com/{source_id}",
        "requested_url": f"https://example.com/{source_id}",
        "captured_title": f"Title {source_id}",
        "kind": "evidence",
        "access_completeness": "full",
        "identity_status": "match",
        "body_path": rel,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "captured_at": "2026-09-04T12:00:00+08:00",
        "accessed_at": "2026-09-04T12:00:00+08:00",
        "publication_time": "2026-09-03T16:00:00+00:00",
        "publication_time_precision": "hour",
        "event_time": "2026-09-03T16:00:00+00:00",
        "event_time_precision": "hour",
    }


def _coverage(source_ids: list[str] | None = None) -> list[dict]:
    ids = source_ids or [f"cov-{idx}" for idx in range(len(CHECKS))]
    return [
        {"domain": domain, "check": check, "status": "checked", "source_ids": [source_id]}
        for (domain, check), source_id in zip(CHECKS, ids, strict=True)
    ]


def _item(**overrides) -> dict:
    data = {
        "item_id": "macro:oil-rates",
        "domain": "macro_upstream",
        "title": "油价重新成为利率路径的上游变量",
        "event_time": "2026-09-03T16:00:00+00:00",
        "publication_time": "2026-09-03T16:00:00+00:00",
        "source_url": "https://example.com/item-src",
        "source_id": "item-src",
        "source_authority": 5,
        "evidence_status": "primary_read",
        "themes": ["energy", "rates", "inflation"],
        "fact": "商业原油库存下降，供应风险仍在。",
        "transmission": "能源成本可能重新进入通胀，并提高长久期资产的估值门槛。",
        "affected_dimensions": ["valuation", "financing_cost", "risk"],
        "impact_score": 5,
        "changed_since_last_run": True,
        "action_type": "monitor_trigger",
        "next_research_action": "核验就业与通胀数据是否确认能源价格的传导。",
        "falsifier": "若油价回落且核心通胀继续降温，这条压力路径应下调。",
        "prior_view": "此前把能源当作已定价的背景。",
        "evidence_delta": "商业原油库存下降，供应风险仍在。",
        "interpretation": "能源成本可能重新进入通胀核验。",
        "counterevidence": "若油价回落且核心通胀继续降温，应下调。",
        "thesis_key": "macro_upstream:energy",
        "opportunity_hypothesis": "供应约束可能改变产业利润分配。",
        "affected_companies": "相关供应商；具体收入敞口待核实。",
        "expectation_gap": "市场预期尚未获得可靠一致数据，不能称已低估。",
        "valuation_context": "估值数据缺口，暂不判断价格吸引力。",
    }
    data.update(overrides)
    return data


def _packet(run_dir: Path, items: list[dict], coverage: list[dict] | None = None) -> dict:
    sources = [_write_source(run_dir, f"cov-{idx}") for idx in range(len(CHECKS))]
    sources.append(_write_source(run_dir, "item-src", "商业原油库存下降，供应风险仍在。"))
    return {
        "schema_version": "upstream-radar-packet-v2",
        "as_of": AS_OF.isoformat(),
        "sources": sources,
        "coverage": coverage or _coverage(),
        "items": items,
    }


def test_objective_is_upstream_macro_and_ai_physical_infrastructure():
    objective = load_objective(CONFIG)

    assert set(objective.required_checks) == {"macro_upstream", "ai_upstream", "company_events", "market_interpretation"}
    assert "energy_geopolitics" in objective.required_checks["macro_upstream"]
    assert "power_grid_cooling_datacenters" in objective.required_checks["ai_upstream"]
    assert "max_items" not in CONFIG.read_text(encoding="utf-8")
    assert not hasattr(objective, "max_items")


def test_selection_keeps_macro_and_ai_upstream_but_rejects_generic_noise(tmp_path):
    objective = load_objective(CONFIG)
    ai_item = _item(
        item_id="ai:datacenter-power",
        domain="ai_upstream",
        title="数据中心交付约束开始转向电力和散热",
        themes=["power", "cooling", "datacenter"],
        transmission="机架能否按时通电，决定 AI 资本开支何时转成收入和现金流。",
        affected_dimensions=["cash_flow", "supply_constraint"],
        action_type="recheck_assumption",
        next_research_action="对照数据中心订单、并网进度和基础设施公司的收入兑现。",
        falsifier="若并网与交付周期没有拉长，这个瓶颈判断应下调。",
        thesis_key="ai_upstream:power",
        prior_view="此前把瓶颈主要放在芯片。",
        evidence_delta="电力和散热开始卡住交付。",
        interpretation="AI 资本开支兑现要看通电而不是只看订单。",
        counterevidence="若并网与交付周期没有拉长，应下调。",
    )
    noise = _item(
        item_id="noise:celebrity",
        domain="media",
        title="名人谈 AI",
        themes=["celebrity"],
        transmission="",
        affected_dimensions=[],
        impact_score=2,
    )

    result = evaluate_packet(_packet(tmp_path, [_item(), ai_item, noise]), objective, run_dir=tmp_path)

    assert result.status == "pass"
    assert [item.item_id for item in result.selected] == ["macro:oil-rates", "ai:datacenter-power"]
    assert any(row["item_id"] == "noise:celebrity" for row in result.rejected)


def test_missing_required_coverage_fails_closed(tmp_path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_item()])
    packet["coverage"] = [row for row in packet["coverage"] if row["check"] != "power_grid_cooling_datacenters"]

    result = evaluate_packet(packet, objective, run_dir=tmp_path)

    # A coverage gap no longer holds back qualified items; it is recorded as a gap.
    assert result.outcome == "push"
    assert any("power_grid_cooling_datacenters" in gap for gap in result.gaps)
    # With nothing to publish, silence would hide the unchecked lane: fail closed.
    packet["items"] = []
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert result.status == "fail"
    assert any("power_grid_cooling_datacenters" in error for error in result.errors)


def test_zero_push_is_valid_only_after_complete_checked_no_change_coverage(tmp_path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [])
    packet["coverage"] = [{**row, "status": "checked_no_change"} for row in packet["coverage"]]

    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    brief = render_reader_brief(result, objective)

    assert result.status == "pass"
    assert result.outcome == "no_push"
    assert brief == ""


def test_trade_instruction_blocks_the_run_instead_of_becoming_research_action(tmp_path):
    objective = load_objective(CONFIG)
    unsafe = _item(next_research_action="建议加仓能源股。")

    result = evaluate_packet(_packet(tmp_path, [unsafe]), objective, run_dir=tmp_path)

    assert result.status == "fail"
    assert any("advisory boundary" in error for error in result.errors)


def test_outputs_include_reader_brief_and_product_receipt(tmp_path):
    objective = load_objective(CONFIG)
    stale = _item(item_id="macro:stale", event_time="2026-08-01T00:00:00+08:00", publication_time="2026-08-01T00:00:00+08:00")
    result = evaluate_packet(_packet(tmp_path, [_item(), stale]), objective, run_dir=tmp_path)

    paths = write_outputs(result, objective, tmp_path / "output")
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    brief = paths["brief"].read_text(encoding="utf-8")

    assert receipt["status"] == "pass"
    assert receipt["outcome"] == "push"
    assert receipt["selected_items"] == 1
    assert receipt["rejected_items"] == 1
    assert receipt["rejected"][0]["item_id"] == "macro:stale"
    assert "stale_event" in receipt["rejected"][0]["reasons"]
    assert receipt["claim_sent"] is False
    assert "接下来核验" in brief
    assert "应下调" in brief
    assert "应下调，当前判断应下调" not in brief
    assert "买入" not in brief
    assert "卖出" not in brief
    assert "仓位" not in brief
    assert "[来源](https://example.com/item-src)" in brief


def test_renderer_spaces_an_english_name_after_the_chinese_conditional(tmp_path):
    objective = load_objective(CONFIG)
    candidate = _item(falsifier="Broadcom 指引未兑现，这条判断应下调")
    result = evaluate_packet(_packet(tmp_path, [candidate]), objective, run_dir=tmp_path)

    brief = render_reader_brief(result, objective)

    assert "若 Broadcom 指引未兑现" in brief
    assert "若Broadcom" not in brief


def test_preflight_keeps_six_coverage_and_does_not_treat_missing_prior_as_no_change():
    objective = load_objective(CONFIG)
    checks = required_coverage_checks(objective)
    payload = build_preflight(objective, AS_OF, None, reason="missing")

    assert len(checks) == 8
    assert objective.max_age_hours == 72
    assert payload["preflight_status"] == "blocked"
    assert payload["wakeAgent"] is True
    assert payload["forbid_no_change_claim"] is True
    assert payload["does_not_replace_live_body_verification"] is True
    assert payload["required_this_round"]["coverage_count"] == 8
    assert payload["required_this_round"]["max_age_hours"] == 72
    assert payload["required_this_round"]["no_item_quota"] is True
    assert "brief" not in payload
    assert "买卖" in payload["required_this_round"]["advisory_boundary"]
    assert "交易执行建议" in payload["required_this_round"]["advisory_boundary"]
    assert payload["manual_audit_correction"]["question"]
