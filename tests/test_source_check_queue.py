from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from investment_os.source_check_queue import (
    build_official_macro_source_targets,
    build_source_check_tasks,
    render_source_check_queue,
    run,
)
from investment_os.source_verification_crosswalk import load_source_verification_seed
from investment_os.us_china_pilot import scan_boundary, scan_external_note_quality


def _write_seed(path: Path) -> None:
    rows = [
        {
            "expert_symbol": "theme:ai_infrastructure",
            "expert_signal_claim": "AI infrastructure bottlenecks may be spreading beyond GPUs",
            "verification_topic": "Full-stack data center infrastructure scope",
            "source_type": "SEC filing",
            "source_name": "NVIDIA FY2025 Form 10-K",
            "source_date": "2025-01-26",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm",
            "evidence_direction": "support",
            "evidence_strength": "verified",
            "evidence_excerpt": "NVIDIA describes Blackwell as data center scale infrastructure including GPUs, CPUs, DPUs, interconnects, switch chips, systems, and networking adapters.",
            "cannot_prove": "It does not prove which component is currently binding or who captures the economics.",
            "next_action": "Map the component stack to supplier capacity, pricing, lead time, and margin evidence.",
            "status": "ok",
        },
        {
            "expert_symbol": "theme:photonics_cpo",
            "expert_signal_claim": "Photonics weakness may reflect disputed narrative rather than settled fundamentals",
            "verification_topic": "Optical and AI networking relevance",
            "source_type": "SEC filing",
            "source_name": "Broadcom FY2025 Form 10-K",
            "source_date": "2025-11-02",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1730168/000173016825000121/avgo-20251102.htm",
            "evidence_direction": "mixed",
            "evidence_strength": "verified",
            "evidence_excerpt": "Broadcom says its AI semiconductor solutions include Ethernet switching silicon, NICs, PHYs and optical components.",
            "cannot_prove": "It does not resolve CPO delay claims, hyperscaler capex rumors, or vendor-specific deployment timing.",
            "next_action": "Check NVIDIA, hyperscaler, Broadcom, and optical-vendor filings/calls for deployment timing and capex guidance.",
            "status": "partial",
        },
        {
            "expert_symbol": "theme:physical_ai_supply_chain",
            "expert_signal_claim": "Physical AI component exposure may sit upstream before pure-play public companies emerge",
            "verification_topic": "Upstream physical-AI component revenue linkage",
            "source_type": "verification gap",
            "source_name": "No audited source inspected yet",
            "source_date": "2026-07-05",
            "source_url": "",
            "evidence_direction": "gap",
            "evidence_strength": "blocked",
            "evidence_excerpt": "No primary source in this seed links specific upstream components to audited revenue exposure.",
            "cannot_prove": "Cannot support company-level exposure or economics until revenue/customer linkage is inspected.",
            "next_action": "Inspect supplier filings, segment revenue, customer concentration, and product disclosures.",
            "status": "missing",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_build_source_check_tasks_turns_gaps_and_partials_into_timed_tasks(tmp_path: Path):
    seed = tmp_path / "source_verification_seed.csv"
    _write_seed(seed)
    items = load_source_verification_seed(seed)

    tasks = build_source_check_tasks(items, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert len(tasks) == 2
    assert {task.queue_status for task in tasks} == {"open"}
    assert [task.priority for task in tasks] == ["P0", "P1"]
    assert tasks[0].symbol == "theme:physical_ai_supply_chain"
    assert tasks[0].cadence == "weekly_until_resolved"
    assert tasks[0].next_check_date == "2026-07-08"
    assert "supplier filings" in tasks[0].source_targets
    assert tasks[1].symbol == "theme:photonics_cpo"
    assert tasks[1].cadence == "biweekly_until_resolved"
    assert tasks[1].next_check_date == "2026-07-19"
    assert "deployment timing" in tasks[1].source_targets
    assert all("source_url" in task.success_criteria for task in tasks)


def test_render_source_check_queue_is_forwardable_and_boundary_safe(tmp_path: Path):
    seed = tmp_path / "source_verification_seed.csv"
    _write_seed(seed)
    items = load_source_verification_seed(seed)
    tasks = build_source_check_tasks(items, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    text = render_source_check_queue(tasks, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "Timed Source-Check Queue" in text
    assert "open verification tasks" in text
    assert "theme:physical_ai_supply_chain" in text
    assert "2026-07-08" in text
    assert "source_url" in text
    assert "does not provide portfolio allocation" in text
    assert all(count == 0 for count in scan_external_note_quality(text).values())
    assert all(count == 0 for count in scan_boundary(text).values())


def test_source_check_queue_run_writes_csv_markdown_json_and_quality_scan(tmp_path: Path):
    seed = tmp_path / "source_verification_seed.csv"
    out_dir = tmp_path / "out"
    _write_seed(seed)

    result = run([seed], out_dir=out_dir, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert result.queue_csv_path.exists()
    assert result.queue_json_path.exists()
    assert result.queue_md_path.exists()
    assert result.quality_scan_path.exists()
    rows = list(csv.DictReader(result.queue_csv_path.read_text(encoding="utf-8").splitlines()))
    quality_scan = json.loads(result.quality_scan_path.read_text(encoding="utf-8"))
    assert [row["priority"] for row in rows] == ["P0", "P1"]
    assert rows[0]["task_id"].startswith("SCQ-20260705-")
    assert rows[0]["queue_status"] == "open"
    assert all(count == 0 for count in quality_scan.values())


def test_fed_and_treasury_targets_stay_in_queue_until_evidence_is_fetched():
    tasks = build_official_macro_source_targets(datetime(2026, 7, 8, tzinfo=timezone.utc))

    assert {task.symbol for task in tasks} == {"FOMC", "UST_YIELD_CURVE"}
    assert all(task.queue_status == "open" for task in tasks)
    assert all(task.source_status == "source_target_only" for task in tasks)
    assert all(task.current_evidence == "" for task in tasks)
