from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investment_os import source_cache


def test_source_cache_roundtrips_text_and_json(tmp_path, monkeypatch):
    monkeypatch.setenv("INVEST_ADVISOR_CACHE_DIR", str(tmp_path / "cache"))
    key = source_cache.cache_key("AAPL", "10-K", "0000")

    text, path = source_cache.read_text("sec", key, ".md")
    assert text is None
    assert str(path).endswith(".md")

    written = source_cache.write_text("sec", key, "hello", ".md")
    text, path = source_cache.read_text("sec", key, ".md")

    assert path == written
    assert text == "hello"

    source_cache.write_json("sec", key, ["a", "b"], ".json")
    data, _ = source_cache.read_json("sec", key, ".json")
    assert data == ["a", "b"]


def test_source_cache_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("INVEST_ADVISOR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("INVEST_ADVISOR_DISABLE_CACHE", "1")
    key = source_cache.cache_key("disabled")

    path = source_cache.write_text("sec", key, "hello", ".md")
    text, read_path = source_cache.read_text("sec", key, ".md")

    assert path == read_path
    assert text is None
    assert not path.exists()


def test_source_cache_record_preserves_retrieval_time_url_and_stale_label(tmp_path, monkeypatch):
    monkeypatch.setenv("INVEST_ADVISOR_CACHE_DIR", str(tmp_path / "cache"))
    retrieved_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    key = source_cache.cache_key("fred", "DGS10")
    source_cache.write_record(
        "fred",
        key,
        {"observation_date": "2026-06-30", "value": 4.2},
        source_url="https://fred.test/DGS10",
        retrieved_at=retrieved_at,
    )

    fresh, _ = source_cache.read_record(
        "fred", key, now=retrieved_at + timedelta(hours=1), max_age=timedelta(days=1)
    )
    stale, _ = source_cache.read_record(
        "fred", key, now=retrieved_at + timedelta(days=2), max_age=timedelta(days=1), allow_stale=True
    )

    assert fresh["freshness_status"] == "current"
    assert fresh["source_url"] == "https://fred.test/DGS10"
    assert stale["freshness_status"] == "stale"


def test_stale_source_cache_is_not_returned_without_explicit_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("INVEST_ADVISOR_CACHE_DIR", str(tmp_path / "cache"))
    retrieved_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    key = source_cache.cache_key("fred", "DGS2")
    source_cache.write_record(
        "fred", key, {"value": 4.0}, source_url="https://fred.test/DGS2", retrieved_at=retrieved_at
    )

    record, _ = source_cache.read_record(
        "fred", key, now=retrieved_at + timedelta(days=2), max_age=timedelta(days=1)
    )

    assert record is None
