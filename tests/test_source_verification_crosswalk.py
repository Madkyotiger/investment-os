from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from investment_os.source_verification_crosswalk import (
    EXPERT_SOURCE_VERIFICATION_CATEGORIES,
    load_source_verification_seed,
    render_source_verification_crosswalk,
    run,
)
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


def test_load_source_verification_seed_maps_sources_to_evidence_items(tmp_path: Path):
    seed = tmp_path / "source_verification_seed.csv"
    _write_seed(seed)

    items = load_source_verification_seed(seed)

    assert len(items) == 2
    assert {item.category for item in items} <= EXPERT_SOURCE_VERIFICATION_CATEGORIES
    assert items[0].category == "expert_source_verification"
    assert items[0].status == "ok"
    assert items[1].category == "expert_source_gap"
    assert items[1].status == "missing"
    assert "Evidence direction=support" in items[0].note
    assert "Cannot prove:" in items[0].note
    assert "Next action:" in items[0].note


def test_render_source_verification_crosswalk_keeps_source_checks_bounded(tmp_path: Path):
    seed = tmp_path / "source_verification_seed.csv"
    _write_seed(seed)
    items = load_source_verification_seed(seed)

    crosswalk = render_source_verification_crosswalk(items, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "Public Expert Signal Source Verification Crosswalk" in crosswalk
    assert "Expert signal → Auditable source → What it verifies → What remains unproven → Next action" in crosswalk
    assert "verified" in crosswalk
    assert "No audited source inspected yet" in crosswalk
    assert "does not turn expert signals into conclusions" in crosswalk
    assert all(count == 0 for count in scan_external_note_quality(crosswalk).values())
    assert all(count == 0 for count in scan_boundary(crosswalk).values())


def test_source_verification_run_writes_ledger_crosswalk_and_quality_scan(tmp_path: Path):
    seed = tmp_path / "source_verification_seed.csv"
    out_dir = tmp_path / "out"
    _write_seed(seed)

    result = run([seed], out_dir=out_dir, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert result.ledger_csv_path.exists()
    assert result.ledger_json_path.exists()
    assert result.crosswalk_path.exists()
    assert result.quality_scan_path.exists()
    ledger_rows = list(csv.DictReader(result.ledger_csv_path.read_text(encoding="utf-8").splitlines()))
    quality_scan = json.loads(result.quality_scan_path.read_text(encoding="utf-8"))
    assert len(ledger_rows) == 2
    assert {row["category"] for row in ledger_rows} <= EXPERT_SOURCE_VERIFICATION_CATEGORIES
    assert all(count == 0 for count in quality_scan.values())
