from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from investment_os.investment_decision_support import (
    build_theme_read,
    render_daily_brief,
    render_detailed_pack,
    run,
    scan_investment_output_quality,
)
from investment_os.us_china_pilot import scan_boundary, scan_external_note_quality


def _write_ledger(path: Path) -> None:
    rows = [
        {
            "symbol": "theme:memory_passives",
            "category": "expert_source_verification",
            "claim": "Memory demand and DRAM supply allocation",
            "value": "Micron reports strong data center memory demand and DRAM supply shifting toward high-value data center markets.",
            "source": "SEC filing: Micron FY2025 Form 10-K",
            "as_of_date": "2025-08-28",
            "freshness": "source_verification_verified",
            "status": "ok",
            "url": "https://www.sec.gov/example/micron",
            "note": "Expert signal checked: Memory and passives may remain bottlenecked despite attention rotation; Evidence direction=support; Evidence strength=verified; Cannot prove: Does not prove HBM allocation duration.; Next action: Add HBM capacity and supplier margin evidence.",
        },
        {
            "symbol": "theme:datacenter_power",
            "category": "expert_source_verification",
            "claim": "Data center power and thermal demand",
            "value": "Vertiv says data center power demand is surging and describes power and thermal management work.",
            "source": "Annual report: Vertiv 2025 Annual Report",
            "as_of_date": "2025-12-31",
            "freshness": "source_verification_verified",
            "status": "ok",
            "url": "https://www.vertiv.com/example",
            "note": "Expert signal checked: Datacenter power infrastructure may be emerging as a bottleneck; Evidence direction=support; Evidence strength=verified; Cannot prove: Does not prove grid timing.; Next action: Add utility interconnect queues and supplier backlog evidence.",
        },
        {
            "symbol": "theme:photonics_cpo",
            "category": "expert_source_verification",
            "claim": "Optical and AI networking relevance",
            "value": "Broadcom says AI semiconductor solutions include Ethernet silicon, NICs, PHYs and optical components.",
            "source": "SEC filing: Broadcom FY2025 Form 10-K",
            "as_of_date": "2025-11-02",
            "freshness": "source_verification_verified",
            "status": "partial",
            "url": "https://www.sec.gov/example/broadcom",
            "note": "Expert signal checked: Photonics weakness may reflect disputed narrative rather than settled fundamentals; Evidence direction=mixed; Evidence strength=verified; Cannot prove: Does not resolve CPO delay claims or deployment timing.; Next action: Check NVIDIA, Meta, Broadcom and optical-vendor filings for deployment timing.",
        },
        {
            "symbol": "theme:physical_ai_supply_chain",
            "category": "expert_source_gap",
            "claim": "Upstream physical-AI component revenue linkage",
            "value": "No primary source links upstream components to audited revenue exposure.",
            "source": "Verification gap: No audited source inspected yet",
            "as_of_date": "2026-07-05",
            "freshness": "source_verification_blocked",
            "status": "missing",
            "url": "",
            "note": "Expert signal checked: Physical AI component exposure may sit upstream before pure-play public companies emerge; Evidence direction=gap; Evidence strength=blocked; Cannot prove: Cannot support company-level exposure or economics until supplier revenue and customer evidence are inspected.; Next action: Inspect supplier filings, segment revenue and customer concentration.",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_queue(path: Path) -> None:
    rows = [
        {
            "task_id": "SCQ-20260705-001",
            "symbol": "theme:physical_ai_supply_chain",
            "priority": "P0",
            "cadence": "weekly_until_resolved",
            "created_at": "2026-07-05",
            "next_check_date": "2026-07-08",
            "queue_status": "open",
            "source_status": "missing",
            "evidence_direction": "gap",
            "evidence_strength": "blocked",
            "expert_signal": "Physical AI component exposure may sit upstream before pure-play public companies emerge",
            "verification_topic": "Upstream physical-AI component revenue linkage",
            "current_evidence": "No primary source links upstream components to audited revenue exposure.",
            "source_targets": "Inspect supplier filings, segment revenue, customer concentration, product disclosures, and shipment/capacity data.",
            "success_criteria": "Add source URL, source date, source excerpt and remaining uncertainty.",
            "source_gap": "Cannot support company-level exposure or economics until supplier evidence is inspected.",
            "source_url": "",
        }
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_render_detailed_pack_turns_sources_into_investor_useful_read(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    queue = tmp_path / "queue.csv"
    _write_ledger(ledger)
    _write_queue(queue)
    themes = build_theme_read(ledger, queue)

    detailed = render_detailed_pack(themes, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "AI 基建：研究时间先放哪" in detailed
    assert "最先花时间的两条线" in detailed
    assert "内存 / 被动件" in detailed
    assert "机房电力 / 散热" in detailed
    assert "留在观察区" in detailed
    assert "现在先别急" in detailed
    assert "会改变判断的几个信号" in detailed
    assert "不是交易建议" in detailed
    assert all(count == 0 for count in scan_external_note_quality(detailed).values())
    assert all(count == 0 for count in scan_boundary(detailed).values())
    assert all(count == 0 for count in scan_investment_output_quality(detailed).values())


def test_render_daily_brief_is_phone_sized_and_not_technical(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    queue = tmp_path / "queue.csv"
    _write_ledger(ledger)
    _write_queue(queue)
    themes = build_theme_read(ledger, queue)

    brief = render_daily_brief(themes, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "今天先放一个判断" in brief
    assert "内存 / 被动件" in brief
    assert "观察区" in brief
    assert "先别急" in brief
    assert "今天最该做的动作" in brief
    assert "Evidence Ledger" not in brief
    assert "source verification" not in brief.lower()
    assert "P0" not in brief
    assert len(brief) < 1400
    assert all(count == 0 for count in scan_external_note_quality(brief).values())
    assert all(count == 0 for count in scan_investment_output_quality(brief).values())


def test_run_writes_detailed_and_brief_outputs(tmp_path: Path):
    ledger = tmp_path / "ledger.csv"
    queue = tmp_path / "queue.csv"
    out_dir = tmp_path / "out"
    _write_ledger(ledger)
    _write_queue(queue)

    result = run(ledger, queue, out_dir=out_dir, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert result.detailed_path.exists()
    assert result.brief_path.exists()
    assert result.quality_scan_path.exists()
    scan = json.loads(result.quality_scan_path.read_text(encoding="utf-8"))
    assert all(count == 0 for count in scan.values())
    assert "今天最该做的动作" in result.brief_path.read_text(encoding="utf-8")
