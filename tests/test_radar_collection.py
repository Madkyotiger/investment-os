import json
from datetime import date
from pathlib import Path

from investment_os.cli import main
from investment_os.radar_collection import build_collection_report, render_markdown


def _write_run(root: Path, day: str, run: str, *, status: str = "pass", blocked_source: bool = False) -> None:
    run_dir = root / day / run
    (run_dir / "output").mkdir(parents=True)
    sources = [
        {"source_id": "s1", "url": "https://www.example.com/a", "kind": "evidence", "access_completeness": "full", "identity_status": "match"},
        {"source_id": "s2", "url": "https://data.example.org/b", "kind": "locator", "access_completeness": "blocked"},
    ]
    if blocked_source:
        sources.append({"source_id": "s3", "url": "https://paywalled.example.net/c", "kind": "evidence", "access_completeness": "blocked", "identity_status": "unverified"})
    packet = {
        "sources": sources,
        "coverage": [{"domain": "macro", "check": "rates", "status": "checked", "source_ids": ["s1"]}],
        "research_gaps": ["LME 原始行情页未打开"],
    }
    receipt = {
        "status": status,
        "outcome": "push" if status == "pass" else "blocked",
        "selected_items": 2 if status == "pass" else 0,
        "rejected_items": 1,
        "rejected": [{"item_id": "x", "reasons": ["stale_event", "low_decision_impact"]}],
        "errors": [] if status == "pass" else ["coverage not usable: macro/rates status=blocked"],
        "gaps": ["s3 blocked"] if blocked_source else [],
        "unreviewed_due_followups": ["k1", "k2"],
        "coverage": [{"domain": "macro", "check": "rates", "status": "checked", "derived_source_count": 1, "notes": "缺口：PPI 未取得。"}],
    }
    (run_dir / "live-packet.json").write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    (run_dir / "output" / "run-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")


def test_collection_report_restates_runs_sources_and_gaps(tmp_path: Path):
    _write_run(tmp_path, "2026-11-09", "073000")
    _write_run(tmp_path, "2026-11-10", "073000", status="fail", blocked_source=True)
    _write_run(tmp_path, "2026-11-01", "073000")  # outside the window

    report = build_collection_report(tmp_path, date(2026, 11, 9), date(2026, 11, 11), required_checks=["rates", "energy"])

    assert [row["run"] for row in report["runs"]] == ["2026-11-09/073000", "2026-11-10/073000"]
    assert report["days_without_a_passing_run"] == ["2026-11-10", "2026-11-11"]
    assert report["blocked_or_failed_runs"] == ["2026-11-10/073000"]
    assert report["coverage"]["rates"] == {"checked": 2}
    assert report["coverage"]["energy"] == {"not_reported": 2}
    assert report["unusable_sources"] == [{
        "run": "2026-11-10/073000", "source_id": "s3", "host": "paywalled.example.net",
        "access_completeness": "blocked", "identity_status": "unverified",
    }]
    assert {"host": "example.com", "usable": 2} in report["source_hosts"]
    assert [row["gap"] for row in report["declared_research_gaps"]] == ["LME 原始行情页未打开"] * 2
    assert report["coverage_notes_mentioning_a_gap"][0]["note"] == "缺口：PPI 未取得。"
    assert report["rejected_reasons"] == {"stale_event": 2, "low_decision_impact": 2}
    assert "| 2026-11-10/073000 | fail blocked | 0 | 3 (1) | 0 | 2 | 0 |" in render_markdown(report)


def test_collection_report_is_reachable_from_the_cli(tmp_path: Path, capsys):
    _write_run(tmp_path / "runs", "2026-11-10", "073000")
    out = tmp_path / "report.md"

    assert main(["radar", "collection-report", "--runs-root", str(tmp_path / "runs"), "--until", "2026-11-10", "--days", "2", "--out", str(out)]) == 0

    assert json.loads(capsys.readouterr().out)["runs"] == 1
    assert "## Gaps declared by the researcher" in out.read_text(encoding="utf-8")
