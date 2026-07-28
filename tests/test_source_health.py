from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investment_os.source_health import SourceHealthStore


NOW = datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc)


def test_source_health_tracks_success_failure_and_last_known_good(tmp_path):
    store = SourceHealthStore(tmp_path / "source-health.json")
    store.record_success("fred", "https://fred.test", NOW, content_hash="sha256:abc")
    store.record_failure(
        "fred",
        {"code": "network_error", "message": "timed out", "transient": True},
        NOW + timedelta(minutes=5),
    )

    health = SourceHealthStore(tmp_path / "source-health.json").get("fred")
    assert health["last_success_at"] == NOW.isoformat()
    assert health["last_failure_at"] == (NOW + timedelta(minutes=5)).isoformat()
    assert health["last_known_good"]["source_url"] == "https://fred.test"
    assert health["last_error"]["code"] == "network_error"


def test_source_health_never_records_secret_values(tmp_path):
    store = SourceHealthStore(tmp_path / "source-health.json")
    store.record_failure(
        "messaging_gateway",
        {"code": "auth", "message": "request failed", "source_url": "https://example.test/path"},
        NOW,
    )
    text = (tmp_path / "source-health.json").read_text(encoding="utf-8")
    assert "token=" not in text


def test_stale_observation_does_not_replace_fresh_last_known_good(tmp_path):
    store = SourceHealthStore(tmp_path / "source-health.json")
    store.record_success(
        "fred:dgs10",
        "https://fred.test?id=DGS10",
        NOW,
        content_hash="sha256:fresh",
        as_of_date="2026-07-10",
        freshness_status="current",
        freshness_threshold_days=5,
        evidence_status="single_source_data",
    )
    store.record_observation(
        "fred:dgs10",
        "https://fred.test?id=DGS10",
        NOW + timedelta(minutes=5),
        content_hash="sha256:stale",
        as_of_date="2026-06-01",
        freshness_status="stale",
        freshness_threshold_days=5,
        evidence_status="stale",
    )

    health = store.get("fred:dgs10")
    assert health["last_known_good"]["content_hash"] == "sha256:fresh"
    assert health["last_observation"]["content_hash"] == "sha256:stale"
    assert health["last_observation_status"] == "stale"
