from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from investment_os.expert_signal_ingest import (
    EXPERT_SIGNAL_CATEGORIES,
    load_expert_signal_seed,
    render_public_expert_signal_crosswalk,
    run,
)
from investment_os.us_china_pilot import scan_boundary, scan_external_note_quality


def _write_seed(path: Path) -> None:
    rows = [
        {
            "symbol": "theme:ai_infrastructure",
            "category": "expert_signal_context",
            "claim": "AI infrastructure bottlenecks may extend beyond GPUs",
            "value": "A public expert signal points to memory, optical networking, power, and packaging as possible constraints.",
            "source": "X public expert signal: @aleabitoreddit",
            "as_of_date": "2026-07-05",
            "freshness": "public_expert_signal",
            "status": "partial",
            "url": "https://x.com/aleabitoreddit/status/2073763512216899825",
            "note": "Evidence strength=weak; verify with supplier filings, capex disclosure, lead times, pricing, and earnings-call evidence.",
        },
        {
            "symbol": "theme:ai_infrastructure",
            "category": "expert_signal_review_question",
            "claim": "Which AI infrastructure bottleneck is economically material?",
            "value": "Review the bottleneck chain from public signal to primary evidence",
            "source": "Evidence Ledger review-rule seed from Serenity deep dive",
            "as_of_date": "2026-07-05",
            "freshness": "derived_from_public_signal",
            "status": "partial",
            "url": "",
            "note": "Question only; does not support any trade decision or final investment conclusion.",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_load_expert_signal_seed_normalizes_review_questions(tmp_path: Path):
    seed = tmp_path / "expert_signal_seed.csv"
    _write_seed(seed)

    items = load_expert_signal_seed(seed)

    assert len(items) == 2
    assert {item.category for item in items} <= EXPERT_SIGNAL_CATEGORIES
    assert all(item.status == "partial" for item in items)
    review_items = [item for item in items if item.category == "expert_signal_review_question"]
    assert review_items
    assert all(item.value.endswith("?") for item in review_items)
    assert all("Question only" in item.note for item in review_items)


def test_render_public_expert_signal_crosswalk_keeps_signals_as_questions(tmp_path: Path):
    seed = tmp_path / "expert_signal_seed.csv"
    _write_seed(seed)
    items = load_expert_signal_seed(seed)

    crosswalk = render_public_expert_signal_crosswalk(items, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "Public Expert Signal Crosswalk" in crosswalk
    assert "Signal → Evidence support/conflict/gap → Research question → Next source" in crosswalk
    assert "not yet verified by primary evidence" in crosswalk
    assert "Which primary evidence would verify or contradict" in crosswalk
    assert "does not provide trade instructions" in crosswalk
    assert all(count == 0 for count in scan_external_note_quality(crosswalk).values())
    assert all(count == 0 for count in scan_boundary(crosswalk).values())


def test_expert_signal_ingest_run_writes_ledger_crosswalk_and_quality_scan(tmp_path: Path):
    seed = tmp_path / "expert_signal_seed.csv"
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
    assert {row["category"] for row in ledger_rows} <= EXPERT_SIGNAL_CATEGORIES
    assert all(count == 0 for count in quality_scan.values())
