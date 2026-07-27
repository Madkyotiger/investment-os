from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .expert_signal_ingest import QUALITY_FORBIDDEN_PHRASES
from .pipeline import DISCLAIMER
from .source_verification_crosswalk import (
    EXPERT_SOURCE_VERIFICATION_CATEGORIES,
    _clean,
    _parse_note,
    load_source_verification_seeds,
)
from .spike1_research_memo import EvidenceItem


@dataclass
class SourceCheckTask:
    task_id: str
    symbol: str
    priority: str
    cadence: str
    created_at: str
    next_check_date: str
    queue_status: str
    source_status: str
    evidence_direction: str
    evidence_strength: str
    expert_signal: str
    verification_topic: str
    current_evidence: str
    source_targets: str
    success_criteria: str
    source_gap: str
    source_url: str = ""


@dataclass
class SourceCheckQueueResult:
    queue_csv_path: Path
    queue_json_path: Path
    queue_md_path: Path
    quality_scan_path: Path


QUEUE_COLUMNS = [
    "task_id",
    "symbol",
    "priority",
    "cadence",
    "created_at",
    "next_check_date",
    "queue_status",
    "source_status",
    "evidence_direction",
    "evidence_strength",
    "expert_signal",
    "verification_topic",
    "current_evidence",
    "source_targets",
    "success_criteria",
    "source_gap",
    "source_url",
]


def _needs_follow_up(item: EvidenceItem) -> bool:
    if item.category not in EXPERT_SOURCE_VERIFICATION_CATEGORIES:
        return False
    parsed = _parse_note(item)
    direction = _clean(parsed.get("Evidence direction", "")).lower()
    strength = _clean(parsed.get("Evidence strength", item.freshness.replace("source_verification_", ""))).lower()
    return item.status != "ok" or item.category.endswith("_gap") or direction in {"gap", "mixed"} or strength in {"weak", "blocked"}


def _priority_for(item: EvidenceItem) -> str:
    parsed = _parse_note(item)
    direction = _clean(parsed.get("Evidence direction", "")).lower()
    strength = _clean(parsed.get("Evidence strength", item.freshness.replace("source_verification_", ""))).lower()
    if item.status == "missing" or item.category.endswith("_gap") or direction == "gap" or strength == "blocked":
        return "P0"
    if item.status == "partial" or direction == "mixed" or strength == "weak":
        return "P1"
    return "P2"


def _cadence_for(priority: str) -> str:
    if priority == "P0":
        return "weekly_until_resolved"
    if priority == "P1":
        return "biweekly_until_resolved"
    return "monthly_refresh"


def _due_delta_for(priority: str) -> int:
    if priority == "P0":
        return 3
    if priority == "P1":
        return 14
    return 30


def build_source_check_tasks(items: list[EvidenceItem], generated_at: datetime | None = None) -> list[SourceCheckTask]:
    generated_at = generated_at or datetime.now(timezone.utc)
    created_at = generated_at.date().isoformat()
    candidates = [item for item in items if _needs_follow_up(item)]
    tasks: list[SourceCheckTask] = []
    sorted_candidates = sorted(candidates, key=lambda item: (_priority_for(item), item.symbol, item.claim, item.source))
    for index, item in enumerate(sorted_candidates, start=1):
        parsed = _parse_note(item)
        priority = _priority_for(item)
        next_check_date = (generated_at.date() + timedelta(days=_due_delta_for(priority))).isoformat()
        direction = _clean(parsed.get("Evidence direction", ""))
        strength = _clean(parsed.get("Evidence strength", item.freshness.replace("source_verification_", "")))
        expert_signal = _clean(parsed.get("Expert signal checked", ""), 280)
        source_targets = _clean(parsed.get("Next action", item.note), 320)
        source_gap = _clean(parsed.get("Cannot prove", ""), 300)
        tasks.append(
            SourceCheckTask(
                task_id=f"SCQ-{generated_at.strftime('%Y%m%d')}-{index:03d}",
                symbol=_clean(item.symbol),
                priority=priority,
                cadence=_cadence_for(priority),
                created_at=created_at,
                next_check_date=next_check_date,
                queue_status="open",
                source_status=item.status,
                evidence_direction=direction,
                evidence_strength=strength,
                expert_signal=expert_signal,
                verification_topic=_clean(item.claim, 220),
                current_evidence=_clean(item.value, 320),
                source_targets=source_targets,
                success_criteria=(
                    "Add or update a source verification row with source_url, source_date, "
                    "evidence_excerpt, cannot_prove, next_action, and a clean quality scan; "
                    "promote only the narrow claim the source actually verifies."
                ),
                source_gap=source_gap,
                source_url=_clean(item.url),
            )
        )
    return tasks


def scan_source_check_queue_quality(text: str) -> dict[str, int]:
    lower_text = text.lower()
    return {phrase: lower_text.count(phrase.lower()) for phrase in QUALITY_FORBIDDEN_PHRASES}


def render_source_check_queue(tasks: list[SourceCheckTask], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    open_tasks = [task for task in tasks if task.queue_status == "open"]
    p0_count = sum(1 for task in open_tasks if task.priority == "P0")
    lines: list[str] = []
    lines.append("# Timed Source-Check Queue")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append(
        f"This queue contains {len(open_tasks)} open verification tasks; {p0_count} are P0 gaps that need the next auditable source before the theme can be upgraded."
    )
    lines.append("")
    lines.append("A task closes only when the evidence ledger gains a clean source verification row. The queue does not provide portfolio allocation, return promises, or execution instructions.")
    lines.append("")
    if not tasks:
        lines.append("- No open source-check tasks were generated.")
        lines.append("")
    else:
        lines.append("| Task | Priority | Next check | Cadence | Theme | Verification gap | Source targets | Success criteria |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for task in tasks:
            lines.append(
                f"| {_clean(task.task_id, 24)} | {_clean(task.priority, 8)} | {_clean(task.next_check_date, 12)} | {_clean(task.cadence, 32)} | "
                f"{_clean(task.symbol, 70)} | {_clean(task.source_gap, 180)} | {_clean(task.source_targets, 220)} | {_clean(task.success_criteria, 220)} |"
            )
        lines.append("")
    lines.append("Next operating rule: missed or partial rows stay in the queue; verified rows leave only after the crosswalk still preserves what remains unproven.")
    lines.append("")
    return "\n".join(lines)


def _write_queue(tasks: list[SourceCheckTask], csv_path: Path, json_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_COLUMNS)
        writer.writeheader()
        for task in tasks:
            writer.writerow(asdict(task))
    json_path.write_text(json.dumps([asdict(task) for task in tasks], ensure_ascii=False, indent=2), encoding="utf-8")


def run(source_verification_seed_paths: Iterable[Path], out_dir: Path, generated_at: datetime | None = None) -> SourceCheckQueueResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at or datetime.now(timezone.utc)
    items = load_source_verification_seeds(source_verification_seed_paths)
    tasks = build_source_check_tasks(items, generated_at=generated_at)
    queue_text = render_source_check_queue(tasks, generated_at=generated_at)
    quality_scan = scan_source_check_queue_quality(queue_text)
    nonzero = {phrase: count for phrase, count in quality_scan.items() if count}
    if nonzero:
        raise RuntimeError(f"Source-check queue quality scan failed: {nonzero}")

    queue_csv_path = out_dir / "source_check_queue.csv"
    queue_json_path = out_dir / "source_check_queue.json"
    queue_md_path = out_dir / "source_check_queue.md"
    quality_scan_path = out_dir / "source_check_queue_quality_scan.json"

    _write_queue(tasks, queue_csv_path, queue_json_path)
    queue_md_path.write_text(queue_text, encoding="utf-8")
    quality_scan_path.write_text(json.dumps(quality_scan, ensure_ascii=False, indent=2), encoding="utf-8")
    return SourceCheckQueueResult(
        queue_csv_path=queue_csv_path,
        queue_json_path=queue_json_path,
        queue_md_path=queue_md_path,
        quality_scan_path=quality_scan_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a timed follow-up queue for unresolved expert source checks.")
    parser.add_argument(
        "--source-verification-seed",
        dest="source_verification_seeds",
        type=Path,
        nargs="+",
        required=True,
        help="CSV seed file(s) used by source_verification_crosswalk.",
    )
    parser.add_argument("--out", type=Path, default=Path("reports/expert-signals"))
    args = parser.parse_args(argv)
    result = run(args.source_verification_seeds, out_dir=args.out)
    print(f"queue_csv={result.queue_csv_path}")
    print(f"queue_json={result.queue_json_path}")
    print(f"queue_md={result.queue_md_path}")
    print(f"quality_scan={result.quality_scan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
