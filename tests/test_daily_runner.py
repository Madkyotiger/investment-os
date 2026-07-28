from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import investment_os.daily_runner as daily_runner
from investment_os.daily_runner import DailyRunError, run_daily
from investment_os.hard_source_collectors import (
    HardSourceCandidate,
    collect_fred_macro_candidates,
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
            counter_explanation="Adjacent official series may disagree.",
            next_primary_source="Adjacent official series.",
            kill_signal="Block if stale or revised.",
            cannot_prove="One observation cannot prove causality.",
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
        lambda: [
            {
                "source": "yfinance",
                "lane": "market_action",
                "source_url": "https://query1.finance.yahoo.com/",
                "code": "download_error",
                "message": "yfinance market snapshot download failed",
                "transient": True,
            }
        ],
    )

    result = run_daily(WATCHLIST, PROFILE, tmp_path / "state.json", tmp_path / "live", strict=True)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["usable_live_sources"] == 1
    assert manifest["blocked_items"] == 1
    assert manifest["source_failure_count"] == 1
    market_failure = next(
        record for key, record in manifest["source_health"].items() if key.startswith("market_yahoo")
    )
    assert market_failure["last_observation_status"] == "failure"


def test_live_material_macro_promotes_while_sec_retrieval_stays_blocked(monkeypatch, tmp_path: Path):
    generated_at = datetime.now(timezone.utc)
    source_date = generated_at.date().isoformat()
    previous_date = (generated_at.date() - timedelta(days=1)).isoformat()
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_series_text",
        lambda series_id: f"observation_date,{series_id}\n{previous_date},4.0\n{source_date},4.1\n",
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
    fred = next(
        candidate
        for candidate in collect_fred_macro_candidates(
            generated_at,
            state_path=tmp_path / "macro-state.json",
        )
        if candidate.item_id.endswith(":DGS10")
    )
    sec = next(
        candidate
        for candidate in collect_sec_recent_filing_candidates(
            {"research": ["ACME"]},
            generated_at,
            symbol_metadata={"ACME": {"market": "US", "sec_filings": True}},
        )
        if candidate.evidence_status == "primary_body_retrieved"
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
    assert first_manifest["promoted_items"] == 1
    assert {row["source"] for row in first_manifest["source_successes"]} == {"FRED fredgraph.csv"}
    assert all(row["retrieved_at"] for row in first_manifest["source_successes"])
    assert sec.title not in first.brief_path.read_text(encoding="utf-8")
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


def test_stale_sec_receipts_are_all_counted_as_blocked(monkeypatch, tmp_path: Path):
    stale = [
        HardSourceCandidate(
            item_id=f"primary_sec:ACME:{kind}",
            lane="company_events",
            title=f"Old SEC {kind}",
            summary="The receipt is old.",
            source="SEC",
            source_type="primary_filing_body_read" if kind == "body" else "primary_sec_recent_filing",
            source_url=f"https://www.sec.gov/Archives/{kind}",
            as_of_date="2026-06-01",
            retrieved_at="2026-07-28T00:00:00+00:00",
            freshness_status="stale",
            freshness_threshold_days=3,
            content_hash="sha256:old" if kind == "body" else "",
            body_read_status="read" if kind == "body" else "metadata_only",
            counter_explanation="The filing may be routine.",
            next_primary_source="A current filing.",
            kill_signal="Block stale evidence.",
            cannot_prove="An old receipt cannot prove a current change.",
        )
        for kind in ("metadata", "body")
    ]
    monkeypatch.setattr(
        "investment_os.daily_runner.collect_hard_source_candidates",
        lambda *_args, **_kwargs: stale,
    )
    monkeypatch.setattr("investment_os.daily_runner.get_last_source_errors", lambda: [])

    result = run_daily(WATCHLIST, PROFILE, tmp_path / "state.json", tmp_path / "live")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["blocked_items"] == 2
    assert manifest["promoted_items"] == 0


def test_source_health_is_granular_per_fred_series(monkeypatch, tmp_path: Path):
    source_date = datetime.now(timezone.utc).date().isoformat()
    candidates = [
        HardSourceCandidate(
            item_id=f"primary_macro:fred:{series}",
            lane="macro_regime",
            title=f"FRED {series}",
            summary="A current official observation.",
            source="FRED fredgraph.csv",
            source_type="primary_macro_fred_live",
            source_url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}",
            as_of_date=source_date,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            freshness_status="current",
            freshness_threshold_days=5,
            content_hash=f"sha256:{series}",
            counter_explanation="Adjacent official series may disagree.",
            next_primary_source="Adjacent official series.",
            kill_signal="Block if stale or revised.",
            cannot_prove="One observation cannot prove causality.",
        )
        for series in ("DGS2", "DGS10")
    ]
    monkeypatch.setattr(
        "investment_os.daily_runner.collect_hard_source_candidates",
        lambda *_args, **_kwargs: candidates,
    )
    monkeypatch.setattr("investment_os.daily_runner.get_last_source_errors", lambda: [])

    result = run_daily(WATCHLIST, PROFILE, tmp_path / "state.json", tmp_path / "live")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    fred_records = {
        key: record for key, record in manifest["source_health"].items() if key.startswith("fred:")
    }

    assert len(fred_records) == 2
    assert all(record["last_success_at"] for record in fred_records.values())


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


def test_reused_output_failure_never_leaves_complete_manifest_mismatching_artifacts(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "topic-state.json"
    out_dir = tmp_path / "reused-output"
    first = run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)
    original_write_json = daily_runner._write_json

    def fail_before_new_manifest(path: Path, payload: object) -> None:
        if path.name == "source_receipt.json":
            raise OSError("injected staged artifact failure")
        original_write_json(path, payload)

    monkeypatch.setattr(daily_runner, "_write_json", fail_before_new_manifest)
    with pytest.raises(OSError, match="injected staged artifact failure"):
        run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)

    if first.manifest_path.exists():
        manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
        assert manifest["run_complete"] is True
        for name, metadata in manifest["artifacts"].items():
            assert _sha256(out_dir / name) == metadata["sha256"]


def test_atomic_directory_publish_failure_restores_previous_complete_run(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "topic-state.json"
    out_dir = tmp_path / "reused-output"
    first = run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)
    original_replace = daily_runner.os.replace

    def fail_staged_directory_publish(source, destination):
        if Path(source).name == "published-run" and Path(destination) == out_dir:
            raise OSError("injected directory publish failure")
        original_replace(source, destination)

    monkeypatch.setattr(daily_runner.os, "replace", fail_staged_directory_publish)
    with pytest.raises(OSError, match="injected directory publish failure"):
        run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)

    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_complete"] is True
    for name, metadata in manifest["artifacts"].items():
        assert _sha256(out_dir / name) == metadata["sha256"]


def test_live_daily_persists_source_health_and_does_not_promote_last_known_good(monkeypatch, tmp_path: Path):
    current_date = datetime.now(timezone.utc).date().isoformat()
    old_candidate = HardSourceCandidate(
        item_id="macro:health",
        lane="macro_regime",
        title="Fetched official observation",
        summary="An official level was retrieved.",
        source="FRED",
        source_type="primary_macro_fred_live",
        source_url="https://fred.example/series",
        as_of_date=current_date,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        content_hash="sha256:health",
        observed_value='{"level": 1.0}',
        freshness_status="current",
        freshness_threshold_days=5,
        thesis_impact="unknown",
        counter_explanation="Adjacent official series may disagree.",
        next_primary_source="Adjacent official series.",
        kill_signal="Block if stale or revised.",
        cannot_prove="One observation cannot prove causality.",
    )
    calls = {"count": 0}

    def fake_collect(*_args, **_kwargs):
        calls["count"] += 1
        return [old_candidate] if calls["count"] == 1 else []

    monkeypatch.setattr("investment_os.daily_runner.collect_hard_source_candidates", fake_collect)
    monkeypatch.setattr(
        "investment_os.daily_runner.get_last_source_errors",
        lambda: []
        if calls["count"] == 1
        else [
            {
                "source": "FRED",
                "source_url": "https://fred.example/series",
                "code": "timeout",
                "message": "timed out",
            }
        ],
    )
    state_path = tmp_path / "state.json"

    run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "live-1")
    second = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "live-2")
    manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    health_path = tmp_path / "state.source-health.json"

    assert health_path.exists()
    assert manifest["source_health"]
    fred_health = next(value for key, value in manifest["source_health"].items() if "fred" in key.lower())
    assert fred_health["last_success_at"]
    assert fred_health["last_failure_at"]
    assert fred_health["last_known_good_status"] == "current"
    assert manifest["promoted_items"] == 0
    assert second.status == "quiet"


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


@pytest.mark.parametrize(
    ("point", "published", "recovered_status"),
    [
        ("journal_created", False, "completed"),
        ("post_publication", True, "quiet"),
        ("pre_state_commit", True, "quiet"),
    ],
)
def test_exact_state_journal_fault_points_are_recoverable_and_rerun_quiet(
    monkeypatch, tmp_path: Path, point: str, published: bool, recovered_status: str
):
    state_path = tmp_path / "topic-state.json"
    out_dir = tmp_path / "interrupted-run"

    def inject(actual: str) -> None:
        if actual == point:
            raise OSError(f"injected {point}")

    monkeypatch.setattr(daily_runner, "_run_fault_injection", inject)
    with pytest.raises(OSError, match=f"injected {point}"):
        run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)

    journal_path = tmp_path / ".topic-state.json.pending.json"
    assert journal_path.exists()
    assert (out_dir / "manifest.json").exists() is published
    assert not state_path.exists()

    monkeypatch.setattr(daily_runner, "_run_fault_injection", lambda _point: None)
    recovered = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "recovery-run", offline=True)

    assert recovered.status == recovered_status
    assert not journal_path.exists()


def test_stale_prepublish_journal_cannot_commit_an_existing_older_output(monkeypatch, tmp_path: Path):
    old_state = tmp_path / "old-state.json"
    out_dir = tmp_path / "reused-output"
    run_daily(WATCHLIST, PROFILE, old_state, out_dir, offline=True)
    state_path = tmp_path / "new-state.json"

    def inject(point: str) -> None:
        if point == "journal_created":
            raise OSError("injected before publish")

    monkeypatch.setattr(daily_runner, "_run_fault_injection", inject)
    with pytest.raises(OSError, match="injected before publish"):
        run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)
    assert not state_path.exists()

    monkeypatch.setattr(daily_runner, "_run_fault_injection", lambda _point: None)
    recovered = run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "recovered", offline=True)
    assert recovered.status == "completed"


def test_recovery_validates_every_published_artifact_before_committing_state(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "topic-state.json"
    out_dir = tmp_path / "interrupted-run"

    def inject(point: str) -> None:
        if point == "post_publication":
            raise OSError("injected after publish")

    monkeypatch.setattr(daily_runner, "_run_fault_injection", inject)
    with pytest.raises(OSError, match="injected after publish"):
        run_daily(WATCHLIST, PROFILE, state_path, out_dir, offline=True)
    (out_dir / "source_receipt.json").write_text("tampered\n", encoding="utf-8")

    monkeypatch.setattr(daily_runner, "_run_fault_injection", lambda _point: None)
    with pytest.raises(DailyRunError, match="run artifact mismatch"):
        run_daily(WATCHLIST, PROFILE, state_path, tmp_path / "recovery", offline=True)

    assert not state_path.exists()
    assert (tmp_path / ".topic-state.json.pending.json").exists()