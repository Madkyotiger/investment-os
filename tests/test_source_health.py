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
        "feishu",
        {"code": "auth", "message": "request failed", "source_url": "https://example.test/path"},
        NOW,
    )
    text = (tmp_path / "source-health.json").read_text(encoding="utf-8")
    assert "token=" not in text
