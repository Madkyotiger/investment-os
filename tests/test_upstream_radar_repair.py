from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from investment_os.radar_store import (
    ingest_run,
    open_db,
    readback_run,
    readback_thesis_state,
    seed_legacy_from_run,
)
from investment_os.upstream_radar import (
    evaluate_packet,
    load_objective,
    render_reader_brief,
    write_outputs,
)
from investment_os.upstream_radar_preflight import build_preflight

CONFIG = Path("configs/upstream_radar.sample.yaml")
AS_OF = datetime.fromisoformat("2026-09-08T07:20:15+08:00")
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_body(run_dir: Path, rel: str, text: str) -> str:
    path = run_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return _sha(path)


def _source(run_dir: Path, source_id: str, body: str, **overrides) -> dict:
    rel = f"evidence/{source_id}.txt"
    digest = _write_body(run_dir, rel, body)
    row = {
        "source_id": source_id,
        "url": f"https://example.com/{source_id}",
        "requested_url": f"https://example.com/{source_id}",
        "captured_title": f"Title {source_id}",
        "kind": "evidence",
        "access_completeness": "full",
        "identity_status": "match",
        "body_path": rel,
        "sha256": digest,
        "captured_at": "2026-09-08T07:18:00+08:00",
        "accessed_at": "2026-09-08T07:18:00+08:00",
        "publication_time": "2026-09-07T12:00:00+00:00",
        "publication_time_precision": "hour",
        "event_time": "2026-09-07T12:00:00+00:00",
        "event_time_precision": "hour",
    }
    row.update(overrides)
    return row


def _coverage(source_ids: list[str] | None = None) -> list[dict]:
    ids = source_ids or [f"cov-{idx}" for idx in range(len(CHECKS))]
    rows = []
    for (domain, check), source_id in zip(CHECKS, ids, strict=True):
        rows.append({"domain": domain, "check": check, "status": "checked", "source_ids": [source_id]})
    return rows


def _qualifying_item(item_id: str, **overrides) -> dict:
    data = {
        "item_id": item_id,
        "domain": "macro_upstream",
        "title": f"事件 {item_id}",
        "event_time": "2026-09-07T12:00:00+00:00",
        "publication_time": "2026-09-07T12:00:00+00:00",
        "source_url": "https://example.com/item-src",
        "source_id": "item-src",
        "source_authority": 5,
        "evidence_status": "primary_read",
        "themes": ["energy", "geopolitics"],
        "fact": "核验过的事实。",
        "transmission": "可能改变风险核验顺序。",
        "affected_dimensions": ["risk", "cycle"],
        "impact_score": 5,
        "changed_since_last_run": True,
        "action_type": "recheck_assumption",
        "next_research_action": "核验下一份流量数据。",
        "falsifier": "若流量恢复，这条判断应下调。",
        "prior_view": "此前只看到配额政策。",
        "evidence_delta": "新增可核验的物理流量下降。",
        "interpretation": "供应风险应从政策转向航运中断。",
        "counterevidence": "未见库存吸收中断的公开数据。",
        "declared_gaps": "",
        "thesis_key": "macro_upstream:energy",
        "opportunity_hypothesis": "供应约束可能改变产业利润分配。",
        "affected_companies": "相关供应商；具体收入敞口待核实。",
        "expectation_gap": "市场预期尚未获得可靠一致数据，不能称已低估。",
        "valuation_context": "估值数据缺口，暂不判断价格吸引力。",
    }
    data.update(overrides)
    return data


def _packet(run_dir: Path, items: list[dict], sources: list[dict] | None = None) -> dict:
    if sources is None:
        sources = [_source(run_dir, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
        item_src = _source(run_dir, "item-src", "核验过的事实。新增可核验的物理流量下降。")
        sources.append(item_src)
        for item in items:
            item.setdefault("source_id", "item-src")
            item.setdefault("source_url", "https://example.com/item-src")
    return {
        "schema_version": "upstream-radar-packet-v2",
        "as_of": AS_OF.isoformat(),
        "run_id": run_dir.name,
        "sources": sources,
        "coverage": _coverage(),
        "items": items,
    }


def test_explicit_empty_final_blocks_push_but_research_only_still_selects(tmp_path: Path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_qualifying_item("macro:flow")])
    research = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert research.status == "pass" and research.outcome == "push"
    for artifact in ({"text": ""}, {"text": "  \n"}, {}, None, {"text": 123}):
        packet["delivery_artifact"] = artifact
        result = evaluate_packet(packet, objective, run_dir=tmp_path)
        assert result.status == "fail" and result.outcome == "blocked"
        assert any("delivery_artifact" in error for error in result.errors)
        paths = write_outputs(result, objective, tmp_path / "output", packet=packet)
        receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
        assert receipt["status"] == "fail" and receipt["outcome"] == "blocked"
        assert paths["delivery_final"].read_text(encoding="utf-8").strip()


def test_writing_block_is_not_overridden_by_final_text_or_no_push(tmp_path: Path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_qualifying_item("macro:flow")])
    packet["delivery_artifact"] = {"text": "已审阅的研究正文。"}
    for gate in (
        {"status": "blocked", "delivery_authorized": False},
        {"status": "pass", "delivery_authorized": False},
        {"status": "pass"},
        None,
    ):
        packet["writing_gate"] = gate
        result = evaluate_packet(packet, objective, run_dir=tmp_path)
        assert result.status == "fail" and result.outcome == "blocked"
        assert any("writing_gate" in error for error in result.errors)
    packet["writing_gate"] = {"status": "pass", "delivery_authorized": True}
    assert evaluate_packet(packet, objective, run_dir=tmp_path).status == "pass"
    packet["items"] = []
    packet["delivery_artifact"] = {"text": ""}
    packet.pop("writing_gate")
    assert evaluate_packet(packet, objective, run_dir=tmp_path).outcome == "no_push"
    packet["writing_gate"] = {"status": "blocked", "delivery_authorized": False}
    assert evaluate_packet(packet, objective, run_dir=tmp_path).outcome == "blocked"


def test_more_than_three_qualifying_events_all_selected(tmp_path: Path):
    objective = load_objective(CONFIG)
    items = [
        _qualifying_item("macro:hormuz-flow", title="霍尔木兹通航下降"),
        _qualifying_item(
            "macro:fx",
            title="储备估值变化需重核流动性",
            themes=["liquidity", "usd"],
            thesis_key="macro_upstream:liquidity",
            impact_score=4,
        ),
        _qualifying_item(
            "ai:dram-2q26-release",
            domain="ai_upstream",
            title="DRAM 2Q 收入报告在9月发布",
            themes=["semiconductor", "memory"],
            thesis_key="ai_upstream:memory",
            observation_period="2Q26",
            publication_time="2026-09-07T00:00:00+08:00",
            event_time="2026-09-07T00:00:00+08:00",
        ),
        _qualifying_item(
            "ai:power",
            domain="ai_upstream",
            title="数据中心电力约束",
            themes=["power", "datacenter"],
            thesis_key="ai_upstream:power",
            affected_dimensions=["supply_constraint", "cash_flow"],
        ),
    ]
    items.extend([
        _qualifying_item("macro:rates", thesis_key="macro_upstream:rates", themes=["rates"]),
        _qualifying_item("macro:growth", thesis_key="macro_upstream:growth", themes=["growth"]),
    ])
    result = evaluate_packet(_packet(tmp_path, items), objective, run_dir=tmp_path)
    assert result.status == "pass"
    assert result.outcome == "push"
    assert len(result.selected) == 6
    assert {item.item_id for item in result.selected} == {row["item_id"] for row in items}


def test_counts_only_coverage_fails(tmp_path: Path):
    objective = load_objective(CONFIG)
    packet = {
        "as_of": AS_OF.isoformat(),
        "coverage": [
            {"domain": domain, "check": check, "status": "checked_no_change", "source_count": 1}
            for domain, check in CHECKS
        ],
        "items": [],
        "sources": [],
    }
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert result.status == "fail"
    assert result.outcome == "blocked"
    assert any("counts-only" in error or "no verified evidence" in error for error in result.errors)


def test_mismatching_hash_and_path_escape_fail(tmp_path: Path):
    objective = load_objective(CONFIG)
    sources = [_source(tmp_path, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    sources[2]["sha256"] = "0" * 64
    result = evaluate_packet(
        {"as_of": AS_OF.isoformat(), "sources": sources, "coverage": _coverage(), "items": []},
        objective,
        run_dir=tmp_path,
    )
    assert result.status == "fail"
    assert any("sha256" in error or "hash" in error for error in result.errors)

    escape_dir = tmp_path / "escape"
    escape_dir.mkdir()
    sources = [_source(escape_dir, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    sources[0]["body_path"] = "../secret.txt"
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    result = evaluate_packet(
        {"as_of": AS_OF.isoformat(), "sources": sources, "coverage": _coverage(), "items": []},
        objective,
        run_dir=escape_dir,
    )
    assert result.status == "fail"
    assert any("escape" in error or "path" in error for error in result.errors)


def test_symlink_escape_fails(tmp_path: Path):
    objective = load_objective(CONFIG)
    outside = tmp_path / "outside.txt"
    outside.write_text("escaped-body", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sources = [_source(run_dir, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    link = run_dir / "evidence" / "cov-0.txt"
    link.unlink()
    os.symlink(outside, link)
    sources[0]["sha256"] = _sha(outside)
    result = evaluate_packet(
        {"as_of": AS_OF.isoformat(), "sources": sources, "coverage": _coverage(), "items": []},
        objective,
        run_dir=run_dir,
    )
    assert result.status == "fail"
    assert any("symlink" in error or "escape" in error for error in result.errors)


def test_partial_is_not_full_read(tmp_path: Path):
    objective = load_objective(CONFIG)
    sources = [_source(tmp_path, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    sources[2]["access_completeness"] = "partial"
    packet = {
        "as_of": AS_OF.isoformat(),
        "sources": sources,
        "coverage": _coverage(),
        "items": [
            _qualifying_item(
                "macro:partial-claim",
                source_id="cov-2",
                source_url="https://example.com/cov-2",
                evidence_status="primary_read",
            )
        ],
    }
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert result.status == "fail"
    assert any("partial" in error or "full-read" in error or "verified evidence" in error for error in result.errors)
    assert any(row["item_id"] == "macro:partial-claim" for row in result.rejected)


def test_excerpt_requires_literal_quote_for_bounded_claim(tmp_path: Path):
    objective = load_objective(CONFIG)
    quote = "Ten-day moving average commodity-ship transits fell to 10/day"
    sources = [_source(tmp_path, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    sources.append(
        _source(
            tmp_path,
            "excerpt-hormuz",
            f"Lead paragraph. {quote}. Rest omitted.",
            access_completeness="excerpt",
            quote=quote,
        )
    )
    ok_item = _qualifying_item(
        "macro:hormuz-excerpt",
        source_id="excerpt-hormuz",
        source_url="https://example.com/excerpt-hormuz",
        evidence_status="secondary_confirmed",
        bounded_quote=quote,
        fact=quote,
    )
    result = evaluate_packet(
        {"as_of": AS_OF.isoformat(), "sources": sources, "coverage": _coverage(), "items": [ok_item]},
        objective,
        run_dir=tmp_path,
    )
    assert result.status == "pass"
    assert result.selected[0].item_id == "macro:hormuz-excerpt"

    bad = dict(ok_item)
    bad["item_id"] = "macro:hormuz-excerpt-missing-quote"
    bad["bounded_quote"] = ""
    result = evaluate_packet(
        {"as_of": AS_OF.isoformat(), "sources": sources, "coverage": _coverage(), "items": [bad]},
        objective,
        run_dir=tmp_path,
    )
    assert any(row["item_id"] == "macro:hormuz-excerpt-missing-quote" for row in result.rejected)


def test_url_identity_mismatch_is_invalid_receipt_and_recovered_source_ok(tmp_path: Path):
    objective = load_objective(CONFIG)
    sources = [_source(tmp_path, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    recovered = _source(
        tmp_path,
        "bls-recovered",
        "Employment Situation Summary - 2026 M08 Results. Nonfarm payrolls.",
        url="https://www.bls.gov/news.release/empsit.nr0.htm",
        requested_url="https://www.bls.gov/news.release/empsit.nr0.htm",
        captured_title="Employment Situation Summary - 2026 M08 Results",
        identity_status="match",
    )
    mismatched = _source(
        tmp_path,
        "bls-mismatch",
        "DRAM Industry Revenue Rises 59.5% QoQ in 2Q26",
        url="https://www.bls.gov/news.release/archives/empsit_09042026.htm",
        requested_url="https://www.bls.gov/news.release/archives/empsit_09042026.htm",
        captured_title="DRAM Industry Revenue Rises 59.5% QoQ in 2Q26 as Supply Expansion Continues to Lag Demand Growth, Says TrendForce",
        identity_status="mismatch",
        access_completeness="blocked",
        recovered_source_id="bls-recovered",
    )
    sources.extend([mismatched, recovered])
    coverage = _coverage()
    coverage[1] = {
        "domain": "macro_upstream",
        "check": "inflation_growth_labor",
        "status": "checked",
        "source_ids": ["bls-mismatch", "bls-recovered"],
    }
    result = evaluate_packet(
        {"as_of": AS_OF.isoformat(), "sources": sources, "coverage": coverage, "items": []},
        objective,
        run_dir=tmp_path,
    )
    assert result.status == "pass"
    derived = next(row for row in result.coverage if row["check"] == "inflation_growth_labor")
    assert derived["derived_source_count"] == 1
    assert "bls-mismatch" not in derived["verified_source_ids"]
    assert derived["invalid_source_ids"] == ["bls-mismatch"]


def test_new_release_with_older_observation_period_is_not_backdated(tmp_path: Path):
    objective = load_objective(CONFIG)
    item = _qualifying_item(
        "ai:dram-2q26-release",
        domain="ai_upstream",
        themes=["semiconductor", "memory"],
        thesis_key="ai_upstream:memory",
        observation_period="2Q26",
        publication_time="2026-09-07T00:00:00+08:00",
        event_time="2026-09-07T00:00:00+08:00",
        title="9月发布的2Q26 DRAM收入报告",
    )
    result = evaluate_packet(_packet(tmp_path, [item]), objective, run_dir=tmp_path)
    assert result.status == "pass"
    selected = result.selected[0]
    assert selected.observation_period == "2Q26"
    assert selected.publication_time.startswith("2026-09-07")
    assert "2026-04" not in selected.event_time
    assert selected.age_hours < 72


def test_no_push_preserves_history_and_same_theme_new_evidence(tmp_path: Path):
    objective = load_objective(CONFIG)
    db_path = tmp_path / "radar-index.sqlite"
    first_dir = tmp_path / "2026-09-07"
    first_dir.mkdir()
    first_packet = _packet(first_dir, [_qualifying_item("macro:opec-pause", title="OPEC 10月暂停加量")])
    first_packet["run_id"] = "2026-09-07"
    first = evaluate_packet(first_packet, objective, run_dir=first_dir)
    write_outputs(first, objective, first_dir / "output", packet=first_packet, run_dir=first_dir, db_path=db_path)

    no_push_dir = tmp_path / "2026-09-08-empty"
    no_push_dir.mkdir()
    sources = [_source(no_push_dir, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    no_push_packet = {
        "schema_version": "upstream-radar-packet-v2",
        "as_of": "2026-09-08T07:20:15+08:00",
        "run_id": "2026-09-08-empty",
        "sources": sources,
        "coverage": [{**row, "status": "checked_no_change"} for row in _coverage()],
        "items": [
            _qualifying_item(
                "macro:fx-low",
                impact_score=2,
                source_id="cov-0",
                source_url="https://example.com/cov-0",
                thesis_key="macro_upstream:liquidity",
            )
        ],
    }
    no_push_packet["followup_updates"] = [{
        "tracking_key": "macro:opec-pause", "status": "open",
        "next_check_at": "2026-09-09T07:15:00+08:00",
        "reason": "本轮检查无新证据，保留问题并于下一轮核验。", "source_ids": ["cov-2"],
    }]
    no_push = evaluate_packet(no_push_packet, objective, run_dir=no_push_dir)
    assert no_push.outcome == "no_push"
    write_outputs(no_push, objective, no_push_dir / "output", packet=no_push_packet, run_dir=no_push_dir, db_path=db_path)

    conn = open_db(db_path)
    state = readback_thesis_state(conn)
    assert any(row["thesis_key"] == "macro_upstream:energy" and row["last_item_id"] == "macro:opec-pause" for row in state)
    empty_run = readback_run(conn, "2026-09-08-empty")
    assert empty_run["outcome"] == "no_push"
    assert any(row["item_id"] == "macro:fx-low" and row["inclusion"] == "excluded" for row in empty_run["candidates"])

    preflight = build_preflight(
        objective,
        AS_OF,
        no_push_dir,
        db_path=db_path,
    )
    assert "brief" not in (preflight.get("prior_run") or {})
    theses = [row["item_id"] for row in preflight["meaningful_thesis_state"]]
    assert "macro:opec-pause" in theses
    assert preflight["same_theme_new_evidence_allowed"] is True
    assert preflight["no_push_does_not_erase_history"] is True

    later_dir = tmp_path / "2026-09-08-hormuz"
    later_dir.mkdir()
    later_item = _qualifying_item("macro:hormuz-flow", title="霍尔木兹通航下降，流量证据新于配额")
    later_packet = _packet(later_dir, [later_item])
    later_packet["run_id"] = "2026-09-08-hormuz"
    later = evaluate_packet(later_packet, objective, run_dir=later_dir)
    assert later.status == "pass"
    assert later.selected[0].item_id == "macro:hormuz-flow"
    write_outputs(later, objective, later_dir / "output", packet=later_packet, run_dir=later_dir, db_path=db_path)
    state = readback_thesis_state(open_db(db_path))
    energy = next(row for row in state if row["thesis_key"] == "macro_upstream:energy")
    assert energy["last_item_id"] == "macro:hormuz-flow"


def test_idempotent_db_ingestion(tmp_path: Path):
    objective = load_objective(CONFIG)
    db_path = tmp_path / "radar-index.sqlite"
    packet = _packet(tmp_path, [_qualifying_item("macro:hormuz-flow")])
    packet["run_id"] = "same-run"
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    conn = open_db(db_path)
    first = ingest_run(conn, packet, result, tmp_path)
    second = ingest_run(conn, packet, result, tmp_path)
    assert first["run_id"] == second["run_id"] == "same-run"
    readback = readback_run(conn, "same-run")
    assert readback["candidate_count"] == 1
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1


def test_legacy_seed_is_unverified_metadata_not_source_rows(tmp_path: Path):
    run_dir = tmp_path / "legacy"
    out = run_dir / "output"
    out.mkdir(parents=True)
    (out / "run-receipt.json").write_text(
        json.dumps({"status": "pass", "outcome": "push", "as_of": "2026-09-07T07:20:46+08:00", "selected_items": 1}),
        encoding="utf-8",
    )
    (out / "reader-brief.md").write_text("# old\n", encoding="utf-8")
    (out / "selected-items.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "macro:opec-october-output-pause-2026-09-06",
                    "domain": "macro_upstream",
                    "title": "OPEC+ 10月不再加量",
                    "event_time": "2026-09-06T00:00:00+02:00",
                    "source_url": "https://www.opec.org/pr-detail/1835613-6-september-2026.html",
                    "fact": "10月要求产量维持在9月水平",
                    "themes": ["energy"],
                }
            ]
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "radar-index.sqlite"
    conn = open_db(db_path)
    seed_legacy_from_run(conn, run_dir)
    state = readback_thesis_state(conn)
    assert state[0]["status"] == "legacy_unverified"
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
    preflight = build_preflight(load_objective(CONFIG), AS_OF, run_dir, db_path=db_path)
    assert preflight["meaningful_thesis_state"][0]["status"] == "legacy_unverified"
    assert "brief" not in (preflight.get("prior_run") or {})
    assert "霍尔木兹" in preflight["manual_audit_correction"]["question"] or "流量" in preflight["manual_audit_correction"]["question"]


def test_bounded_no_push_and_distinct_delivery_artifact(tmp_path: Path):
    objective = load_objective(CONFIG)
    sources = [_source(tmp_path, f"cov-{idx}", f"coverage body {idx}") for idx in range(len(CHECKS))]
    packet = {
        "as_of": AS_OF.isoformat(),
        "sources": sources,
        "coverage": [{**row, "status": "checked_no_change"} for row in _coverage()],
        "items": [],
        "delivery_artifact": {"kind": "human_final", "text": "人工定稿：今日不推送。", "claim_sent": True},
    }
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    brief = render_reader_brief(result, objective)
    assert brief == ""
    assert "没有足以改变研究动作的上游变化" not in brief
    paths = write_outputs(result, objective, tmp_path / "output", packet=packet, run_dir=tmp_path)
    delivery = paths["delivery_final"].read_text(encoding="utf-8")
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    assert delivery == "[SILENT]"
    assert receipt["claim_sent"] is False
    assert receipt["delivery_artifact_stored"] is True
    assert paths["brief"].read_text(encoding="utf-8") != delivery


def test_config_has_no_item_quota():
    objective = load_objective(CONFIG)
    raw = Path("configs/upstream_radar.sample.yaml").read_text(encoding="utf-8")
    assert "max_items" not in raw
    assert not hasattr(objective, "max_items") or getattr(objective, "max_items") in (None, 0)


def test_missing_capture_time_and_wrong_source_url_do_not_pass(tmp_path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_qualifying_item("test:identity")])
    packet["sources"][0].pop("captured_at")
    packet["sources"][0].pop("accessed_at")
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    # The defective source is unusable and recorded; the run is not passed on it.
    assert any("cov-0 missing/invalid captured_at" in gap for gap in result.gaps)
    assert all(row.get("derived_source_count") == 0 for row in result.coverage if "cov-0" in row.get("source_ids", []))
    packet["items"] = []
    assert evaluate_packet(packet, objective, run_dir=tmp_path).status == "fail"
    packet = _packet(tmp_path, [_qualifying_item("test:url", source_url="https://wrong.example/fact")])
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert not result.selected
    assert any("source_url_mismatch" in row["reasons"] for row in result.rejected)


def test_actual_delivery_and_counterevidence_scanned(tmp_path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_qualifying_item("test:counter", counterevidence="建议买入股票")])
    assert evaluate_packet(packet, objective, run_dir=tmp_path).status == "fail"
    packet = _packet(tmp_path, [_qualifying_item("test:final")])
    packet["delivery_artifact"] = {"text": "建议买入股票"}
    assert evaluate_packet(packet, objective, run_dir=tmp_path).status == "fail"


def test_reingesting_older_run_cannot_rewind_meaningful_state(tmp_path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_qualifying_item("test:old")])
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    conn = open_db(tmp_path / "index.sqlite")
    ingest_run(conn, packet, result, tmp_path)
    newer = dict(packet, run_id="newer", as_of="2026-09-08T08:00:00+08:00", items=[_qualifying_item("test:new")])
    newer_result = evaluate_packet(newer, objective, run_dir=tmp_path)
    ingest_run(conn, newer, newer_result, tmp_path)
    ingest_run(conn, packet, result, tmp_path)
    assert readback_thesis_state(conn)[0]["last_item_id"] == "test:new"


def test_reader_text_is_not_visible_worksheet(tmp_path):
    objective = load_objective(CONFIG)
    packet = _packet(tmp_path, [_qualifying_item("test:reader")])
    text = render_reader_brief(evaluate_packet(packet, objective, run_dir=tmp_path), objective)
    assert "增量证据：" not in text
    assert "本文件是渲染稿" not in text
