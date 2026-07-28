from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import investment_os.daily_runner as daily_runner
from investment_os.daily_runner import DailyRunError, run_daily
from investment_os.hard_source_collectors import (
    HardSourceCandidate,
    collect_fred_yield_candidates,
    collect_sec_recent_filing_candidates,
)


WATCHLIST = Path("configs/watchlist.sample.yaml")
PROFILE = Path("configs/profiles.sample.yaml")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(tmp_path: Path, name: str, **kwargs):
    return run_daily(
        WATCHLIST,
        PROFILE,
        tmp_path / "topic-state.json",
        tmp_path / name,
        offline=True,
        **kwargs,
    )


def test_offline_fixture_is_bundled_as_package_data():
    fixture_path = Path(str(daily_runner.OFFLINE_FIXTURE))

    assert fixture_path.is_file()
    assert fixture_path.parent.name == "data"
    assert fixture_path.parent.parent.name == "investment_os"


def test_offline_daily_run_is_deterministic_and_second_run_is_quiet(tmp_path: Path):
    first = _run(tmp_path, "run-1")
    second = _run(tmp_path, "run-2")

    first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    second_state = json.loads(second.run_state_path.read_text(encoding="utf-8"))

    assert first.status == "completed"
    assert first_manifest["result"] == "completed"
    assert first_manifest["promoted_items"] == 2
    assert second.status == "quiet"
    assert second_manifest["result"] == "quiet"
    assert second_manifest["promoted_items"] == 0
    assert second_state["promoted_item_ids"] == []
    assert "没有足够强的变化值得推送" in second.brief_path.read_text(encoding="utf-8")


def test_offline_runs_from_fresh_state_have_identical_artifacts(tmp_path: Path):
    first = run_daily(WATCHLIST, PROFILE, tmp_path / "state-a.json", tmp_path / "a", offline=True)
    second = run_daily(WATCHLIST, PROFILE, tmp_path / "state-b.json", tmp_path / "b", offline=True)

    assert _sha256(first.brief_path) == _sha256(second.brief_path)
    assert _sha256(first.source_receipt_path) == _sha256(second.source_receipt_path)


def test_offline_strict_does_not_fail_on_blocked_candidates(tmp_path: Path):
    result = _run(tmp_path, "strict-offline", strict=True)

    assert result.status == "completed"


def test_live_strict_passes_when_one_usable_source_succeeds(monkeypatch, tmp_path: Path):
    candidates = [
        HardSourceCandidate(
            item_id="macro:usable",
            lane="macro_regime",
            title="Usable official observation",
            summary="A fetched official observation changed.",
            source="FRED",
            source_type="primary_macro_fred_yields_live",
            source_url="https://fred.example/series",
            as_of_date="2026-07-28",
            retrieved_at="2026-07-28T00:00:00+00:00",
            content_hash="sha256:usable",
            evidence_status="single_source_data",
        ),
        HardSourceCandidate(
            item_id="macro:target",
            lane="macro_regime",
            title="Blocked target",
            summary="No observation fetched.",
            source="Federal Reserve",
            source_type="primary_macro_calendar",
            source_url="https://fed.example/calendar",
            as_of_date="2026-07-28",
        ),
    ]
    monkeypatch.setattr("investment_os.daily_runner.collect_hard_source_candidates", lambda *_args, **_kwargs: candidates)
    monkeypatch.setattr(
        "investment_os.daily_runner.get_last_source_errors",
        lambda: [{"source": "SEC", "code": "blocked", "message": "blocked candidate"}],
    )

    result = run_daily(WATCHLIST, PROFILE, tmp_path / "state.json", tmp_path / "live", strict=True)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["usable_live_sources"] == 1
    assert manifest["blocked_items"] == 1
    assert manifest["source_failure_count"] == 1


def test_live_injected_fred_and_sec_evidence_promotes_once_then_rerun_is_quiet(monkeypatch, tmp_path: Path):
    generated_at = datetime.now(timezone.utc)
    source_date = generated_at.date().isoformat()
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_latest",
        lambda series_id: (source_date, {"DGS2": 4.0, "DGS10": 4.5, "DGS30": 4.8}[series_id]),
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._safe_sec_recent",
        lambda: {"0": {"ticker": "ACME", "cik_str": "1234", "title": "Acme"}},
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._latest_sec_filing_for_cik",
        lambda _cik: {
            "form": "8-K",
            "filing_date": source_date,
            "accession": "0001-02-03",
            "primary_doc": "acme.htm",
        },
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._http_text",
        lambda _url, timeout=10: "<html><body>synthetic injected filing body</body></html>",
    )
    fred = collect_fred_yield_candidates(generated_at)[0]
    sec = next(
        candidate
        for candidate in collect_sec_recent_filing_candidates(
            {"research": ["ACME"]},
            generated_at,
            symbol_metadata={"ACME": {"market": "US", "sec_filings": True}},
        )
        if candidate.evidence_status == "primary_body_read"
    )
    monkeypatch.setattr(
        "investment_os.daily_runner.collect_hard_source_candidates",
        lambda *_args, **_kwargs: [fred, sec],
    )
    monkeypatch.setattr("investment_os.daily_runner.get_last_source_errors", lambda: [])
    state_path = tmp_path / "state.json"

    first = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "live-1", strict=True)
    second = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "live-2", strict=True)
    first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))

    assert first.status == "completed"
    assert first_manifest["promoted_items"] == 2
    assert {row["source"] for row in first_manifest["source_successes"]} == {
        "FRED fredgraph.csv",
        "SEC primary filing body",
    }
    assert all(row["retrieved_at"] for row in first_manifest["source_successes"])
    assert second.status == "quiet"
    assert second_manifest["promoted_items"] == 0


def test_live_strict_fails_only_when_every_usable_source_fails(monkeypatch, tmp_path: Path):
    candidates = [
        HardSourceCandidate(
            item_id="macro:target",
            lane="macro_regime",
            title="Blocked target",
            summary="No observation fetched.",
            source="Federal Reserve",
            source_type="primary_macro_calendar",
            source_url="https://fed.example/calendar",
            as_of_date="2026-07-28",
        )
    ]
    monkeypatch.setattr("investment_os.daily_runner.collect_hard_source_candidates", lambda *_args, **_kwargs: candidates)
    monkeypatch.setattr(
        "investment_os.daily_runner.get_last_source_errors",
        lambda: [{"source": "FRED", "code": "timeout", "message": "request timed out"}],
    )

    with pytest.raises(DailyRunError, match="no usable live source succeeded"):
        run_daily(WATCHLIST, PROFILE, tmp_path / "state.json", tmp_path / "live", strict=True)


def test_live_strict_rejects_successful_but_stale_observations(monkeypatch, tmp_path: Path):
    candidates = [
        HardSourceCandidate(
            item_id="macro:stale",
            lane="macro_regime",
            title="Old official observation",
            summary="The fetch succeeded but the observation is outside its cadence window.",
            source="FRED",
            source_type="primary_macro_fred_yields_live",
            source_url="https://fred.example/series",
            as_of_date="2025-01-01",
            retrieved_at="2026-07-28T00:00:00+00:00",
            content_hash="sha256:stale",
            freshness_status="stale",
            evidence_status="single_source_data",
        )
    ]
    monkeypatch.setattr("investment_os.daily_runner.collect_hard_source_candidates", lambda *_args, **_kwargs: candidates)
    monkeypatch.setattr("investment_os.daily_runner.get_last_source_errors", lambda: [])

    with pytest.raises(DailyRunError, match="no usable live source succeeded"):
        run_daily(WATCHLIST, PROFILE, tmp_path / "state.json", tmp_path / "live", strict=True)


def test_manifest_is_written_last_as_completed_run_receipt(tmp_path: Path):
    result = _run(tmp_path, "manifest")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["run_complete"] is True
    assert manifest["mode"] == "offline"
    assert manifest["watchlist"] == str(WATCHLIST)
    assert manifest["profile"] == str(PROFILE)
    assert manifest["topic_state"] == str(tmp_path / "topic-state.json")
    for name, metadata in manifest["artifacts"].items():
        artifact = result.manifest_path.parent / name
        assert artifact.exists()
        assert _sha256(artifact) == metadata["sha256"]


def test_manifest_write_failure_never_advances_durable_topic_state(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "topic-state.json"
    out_dir = tmp_path / "failed-run"
    original_write_json = daily_runner._write_json

    def fail_manifest(path: Path, payload: object) -> None:
        if path.name == "manifest.json":
            raise OSError("injected manifest write failure")
        original_write_json(path, payload)

    monkeypatch.setattr(daily_runner, "_write_json", fail_manifest)
    with pytest.raises(OSError, match="injected manifest write failure"):
        run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)

    assert not state_path.exists()
    assert not (out_dir / "manifest.json").exists()

    monkeypatch.setattr(daily_runner, "_write_json", original_write_json)
    recovered = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "recovered-run", offline=True)
    assert recovered.status == "completed"


def test_completed_receipt_recovers_state_commit_interrupted_after_manifest(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "topic-state.json"
    original_atomic_write_bytes = daily_runner._atomic_write_bytes

    def fail_durable_state(path: Path, content: bytes) -> None:
        if path == state_path:
            raise OSError("injected durable state failure")
        original_atomic_write_bytes(path, content)

    monkeypatch.setattr(daily_runner, "_atomic_write_bytes", fail_durable_state)
    with pytest.raises(OSError, match="injected durable state failure"):
        run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "receipt-complete", offline=True)

    assert not state_path.exists()
    assert (tmp_path / "receipt-complete" / "manifest.json").exists()
    assert (tmp_path / ".topic-state.json.pending.json").exists()

    monkeypatch.setattr(daily_runner, "_atomic_write_bytes", original_atomic_write_bytes)
    next_run = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "after-recovery", offline=True)
    assert next_run.status == "quiet"
    assert state_path.exists()
    assert not (tmp_path / ".topic-state.json.pending.json").exists()