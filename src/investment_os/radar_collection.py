"""What the daily radar actually managed to collect, read from its own run folders.

The report restates facts already written by each run (packet, receipt). It adds no
judgment: deciding which recurring gap deserves a collector, a source route or a rule
change is the reader's job.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPORT_SCHEMA = "radar-collection-report-v1"
USABLE_COMPLETENESS = {"full", "excerpt"}
GAP_MARKERS = ("缺口", "未取得", "未打开", "未读", "没有读到", "无权限", "付费", "gap", "not opened", "paywall", "unavailable")


def _load(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _run_dirs(runs_root: Path, since: date, until: date) -> list[tuple[date, Path]]:
    found: list[tuple[date, Path]] = []
    for day_dir in sorted(runs_root.iterdir()) if runs_root.is_dir() else []:
        try:
            day = date.fromisoformat(day_dir.name)
        except ValueError:
            continue
        if not day_dir.is_dir() or not since <= day <= until:
            continue
        found.extend((day, run_dir) for run_dir in sorted(day_dir.iterdir()) if (run_dir / "live-packet.json").is_file())
    return found


def _host(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().removeprefix("www.") or "unknown"


def build_collection_report(
    runs_root: Path,
    since: date,
    until: date,
    required_checks: list[str] | None = None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    hosts: dict[str, Counter[str]] = {}
    unusable_sources: list[dict[str, str]] = []
    coverage: dict[str, Counter[str]] = {}
    receipt_gaps: list[dict[str, str]] = []
    declared_gaps: list[dict[str, str]] = []
    coverage_gap_notes: list[dict[str, str]] = []
    rejected_reasons: Counter[str] = Counter()
    unreadable_runs: list[str] = []

    for day, run_dir in _run_dirs(runs_root, since, until):
        label = f"{day.isoformat()}/{run_dir.name}"
        packet = _load(run_dir / "live-packet.json")
        if packet is None:
            unreadable_runs.append(label)
            continue
        receipt = _load(run_dir / "output" / "run-receipt.json") or {}
        sources = [row for row in packet.get("sources") or [] if isinstance(row, dict)]
        usable = 0
        for row in sources:
            host = _host(str(row.get("url") or row.get("requested_url") or ""))
            completeness = str(row.get("access_completeness") or "missing")
            identity = str(row.get("identity_status") or "missing")
            is_evidence = row.get("kind") == "evidence"
            ok = is_evidence and completeness in USABLE_COMPLETENESS and identity == "match"
            usable += ok
            hosts.setdefault(host, Counter())["usable" if ok else ("locator" if not is_evidence else "unusable")] += 1
            if is_evidence and not ok:
                unusable_sources.append({
                    "run": label,
                    "source_id": str(row.get("source_id") or ""),
                    "host": host,
                    "access_completeness": completeness,
                    "identity_status": identity,
                })
        seen_checks: set[str] = set()
        for row in receipt.get("coverage") or packet.get("coverage") or []:
            if not isinstance(row, dict):
                continue
            check = str(row.get("check") or "")
            seen_checks.add(check)
            counter = coverage.setdefault(check, Counter())
            counter[str(row.get("status") or "missing")] += 1
            if "derived_source_count" in row and not row.get("derived_source_count"):
                counter["without_usable_source"] += 1
            note = str(row.get("notes") or "")
            if note and any(marker in note.lower() for marker in GAP_MARKERS):
                coverage_gap_notes.append({"run": label, "check": check, "note": note})
        for check in required_checks or []:
            if check not in seen_checks:
                coverage.setdefault(check, Counter())["not_reported"] += 1
        receipt_gaps.extend({"run": label, "gap": str(gap)} for gap in receipt.get("gaps") or [])
        declared_gaps.extend({"run": label, "gap": str(gap)} for gap in packet.get("research_gaps") or [])
        for row in receipt.get("rejected") or []:
            if isinstance(row, dict):
                rejected_reasons.update(str(reason) for reason in row.get("reasons") or [])
        runs.append({
            "run": label,
            "status": receipt.get("status", "no_receipt"),
            "outcome": receipt.get("outcome", ""),
            "selected_items": receipt.get("selected_items"),
            "rejected_items": receipt.get("rejected_items"),
            "errors": [str(error) for error in receipt.get("errors") or []],
            "sources": len(sources),
            "usable_sources": usable,
            "unreviewed_due_followups": len(receipt.get("unreviewed_due_followups") or []),
        })

    days_with_pass = {row["run"][:10] for row in runs if row["status"] == "pass"}
    all_days = [since + timedelta(days=offset) for offset in range((until - since).days + 1)]
    return {
        "schema_version": REPORT_SCHEMA,
        "window": {"since": since.isoformat(), "until": until.isoformat(), "days": len(all_days)},
        "runs": runs,
        "unreadable_runs": unreadable_runs,
        "days_without_a_passing_run": [day.isoformat() for day in all_days if day.isoformat() not in days_with_pass],
        "blocked_or_failed_runs": [row["run"] for row in runs if row["status"] != "pass"],
        "coverage": {check: dict(counter) for check, counter in sorted(coverage.items())},
        "source_hosts": [
            {"host": host, **dict(counter)}
            for host, counter in sorted(hosts.items(), key=lambda pair: (-sum(pair[1].values()), pair[0]))
        ],
        "unusable_sources": unusable_sources,
        "receipt_gaps": receipt_gaps,
        "declared_research_gaps": declared_gaps,
        "coverage_notes_mentioning_a_gap": coverage_gap_notes,
        "rejected_reasons": dict(rejected_reasons.most_common()),
        "restates_run_records_only": True,
    }


def render_markdown(report: dict[str, Any]) -> str:
    window = report["window"]
    runs = report["runs"]
    lines = [
        f"# Radar collection report {window['since']} to {window['until']}",
        "",
        f"- Runs with a packet: {len(runs)}; not passing: {len(report['blocked_or_failed_runs'])}; "
        f"days without a passing run: {', '.join(report['days_without_a_passing_run']) or 'none'}",
        f"- Evidence sources recorded: {sum(row['sources'] for row in runs)}; "
        f"usable: {sum(row['usable_sources'] for row in runs)}; unusable: {len(report['unusable_sources'])}",
        "",
        "## Runs",
        "",
        "| Run | Status | Selected | Sources (usable) | Due questions not reviewed |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {row['run']} | {row['status']} {row['outcome']} | {row['selected_items']} | "
        f"{row['sources']} ({row['usable_sources']}) | {row['unreviewed_due_followups']} |"
        for row in runs
    ]
    lines += ["", "## Coverage checks", "", "| Check | Result counts |", "|---|---|"]
    lines += [
        f"| {check} | {', '.join(f'{key} {value}' for key, value in sorted(counts.items()))} |"
        for check, counts in report["coverage"].items()
    ]
    lines += ["", "## Source hosts", "", "| Host | Usable | Unusable | Locator only |", "|---|---|---|---|"]
    lines += [
        f"| {row['host']} | {row.get('usable', 0)} | {row.get('unusable', 0)} | {row.get('locator', 0)} |"
        for row in report["source_hosts"]
    ]
    for title, key, field in (
        ("Gaps recorded by the validator", "receipt_gaps", "gap"),
        ("Gaps declared by the researcher", "declared_research_gaps", "gap"),
        ("Coverage notes mentioning a gap", "coverage_notes_mentioning_a_gap", "note"),
    ):
        lines += ["", f"## {title}", ""]
        lines += [f"- {row['run']}{' ' + row['check'] if 'check' in row else ''}: {row[field]}" for row in report[key]] or ["- none"]
    if report["rejected_reasons"]:
        lines += ["", "## Rejection reasons", ""]
        lines += [f"- {reason}: {count}" for reason, count in report["rejected_reasons"].items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize what recent radar runs collected and where they fell short.")
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--days", type=int, default=7, help="Window length ending at --until.")
    parser.add_argument("--until", type=date.fromisoformat, default=None, help="Last day of the window (default: today).")
    parser.add_argument("--config", type=Path, help="Radar config; its required checks are reported when a run omits them.")
    parser.add_argument("--out", type=Path, required=True, help="Output path; .md renders Markdown, anything else JSON.")
    args = parser.parse_args(argv)
    until = args.until or date.today()
    since = until - timedelta(days=max(args.days, 1) - 1)
    required: list[str] | None = None
    if args.config:
        from .upstream_radar import load_objective

        required = [check for checks in load_objective(args.config).required_checks.values() for check in checks]
    report = build_collection_report(args.runs_root, since, until, required)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.suffix == ".md":
        args.out.write_text(render_markdown(report), encoding="utf-8")
    else:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "runs": len(report["runs"]),
        "not_passing": len(report["blocked_or_failed_runs"]),
        "days_without_a_passing_run": len(report["days_without_a_passing_run"]),
        "unusable_sources": len(report["unusable_sources"]),
        "declared_research_gaps": len(report["declared_research_gaps"]),
        "output": str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
