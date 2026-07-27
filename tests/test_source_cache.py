from __future__ import annotations

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
