import json
from datetime import datetime, timezone
from pathlib import Path

from investment_os.hard_source_collectors import (
    collect_fred_yield_candidates,
    collect_hard_source_candidates,
    collect_market_move_candidates,
    collect_sec_recent_filing_candidates,
    write_hard_source_candidates,
)

WATCHLIST = Path("configs/watchlist.sample.yaml")


def test_hard_source_collectors_create_primary_and_watchlist_rows():
    candidates = collect_hard_source_candidates(WATCHLIST, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc))
    lanes = {candidate.lane for candidate in candidates}
    source_types = {candidate.source_type for candidate in candidates}

    assert "macro_regime" in lanes
    assert "portfolio_watchlist" in lanes
    assert "primary_macro_calendar" in source_types
    assert "watchlist_config" in source_types
    assert any(candidate.tickers == "NVDA" for candidate in candidates) or any("NVDA" in candidate.tickers for candidate in candidates)
    assert all(candidate.source_url or candidate.source_type == "watchlist_config" for candidate in candidates)


def test_hard_source_candidates_are_written(tmp_path):
    candidates = collect_hard_source_candidates(WATCHLIST, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc))
    csv_path, json_path = write_hard_source_candidates(candidates, tmp_path)

    assert csv_path.exists()
    assert json_path.exists()
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert "cannot_prove" in header
    assert "source_type" in header


def test_fred_live_candidate_uses_verified_data_when_available(monkeypatch):
    def fake_latest(series_id: str):
        return {"DGS2": ("2026-07-07", 4.0), "DGS10": ("2026-07-07", 4.5), "DGS30": ("2026-07-07", 4.8)}[series_id]

    monkeypatch.setattr("investment_os.hard_source_collectors._fred_latest", fake_latest)
    candidates = collect_fred_yield_candidates(datetime(2026, 7, 8, tzinfo=timezone.utc))

    assert candidates[0].source_type == "primary_macro_fred_yields_live"
    assert candidates[0].confidence == "verified_data"
    assert "10Y-2Y spread" in candidates[0].summary
    assert candidates[0].retrieved_at == "2026-07-08T00:00:00+00:00"
    assert candidates[0].thesis_impact == "unknown_narrowed"
    assert candidates[0].observed_value


def test_fred_live_candidate_applies_yaml_stale_threshold_to_observation_dates(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_latest",
        lambda _series_id: ("2026-07-01", 4.0),
    )

    candidate = collect_fred_yield_candidates(datetime(2026, 7, 10, tzinfo=timezone.utc))[0]

    assert candidate.freshness_status == "stale"
    assert candidate.evidence_status == "stale"


def test_fred_live_candidate_treats_threshold_boundary_as_current(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_latest",
        lambda _series_id: ("2026-07-05", 4.0),
    )

    candidate = collect_fred_yield_candidates(datetime(2026, 7, 10, tzinfo=timezone.utc))[0]

    assert candidate.freshness_status == "current"
    assert candidate.freshness_threshold_days == 5


def test_fred_config_falls_back_to_bundled_package_data_outside_checkout(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._fred_latest",
        lambda _series_id: ("2026-07-05", 4.0),
    )

    candidate = collect_fred_yield_candidates(datetime(2026, 7, 10, tzinfo=timezone.utc))[0]

    assert candidate.freshness_status == "current"
    assert candidate.freshness_threshold_days == 5


def test_market_move_candidate_can_be_built_from_snapshot(monkeypatch):
    def fake_snapshot(symbols: list[str]):
        return {
            "SPY": {"date": "2026-07-07", "close": 620.0, "one_day_pct": 0.2, "sixty_day_pct": 8.0},
            "QQQ": {"date": "2026-07-07", "close": 560.0, "one_day_pct": 1.4, "sixty_day_pct": 12.0},
        }

    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", fake_snapshot)
    monkeypatch.setattr("investment_os.hard_source_collectors._download_stooq_snapshot", fake_snapshot)
    candidates = collect_market_move_candidates({"market_proxies": ["SPY", "QQQ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc))

    assert candidates[0].source_type == "market_proxy_prices_live"
    assert candidates[0].confidence == "market_data_cross_checked"
    assert candidates[0].tickers == "SPY,QQQ"
    assert "QQQ" in candidates[0].title
    assert "Stooq" in candidates[0].summary
    assert candidates[0].retrieved_at == "2026-07-08T00:00:00+00:00"
    assert candidates[0].thesis_impact == "unknown_narrowed"
    assert candidates[0].observed_value
    assert candidates[0].content_hash.startswith("sha256:")
    assert candidates[0].freshness_threshold_days == 5


def test_market_move_candidate_uses_configured_snapshot_freshness(monkeypatch):
    snapshot = {
        "SPY": {"date": "2026-06-01", "close": 620.0, "one_day_pct": 1.2, "sixty_day_pct": 8.0},
    }
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: snapshot)
    monkeypatch.setattr("investment_os.hard_source_collectors._download_stooq_snapshot", lambda _symbols: snapshot)

    candidate = collect_market_move_candidates(
        {"market_proxies": ["SPY"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]

    assert candidate.freshness_status == "stale"
    assert candidate.freshness == 1
    assert candidate.evidence_status == "stale"


def test_market_numeric_revision_changes_structured_evidence_but_unchanged_snapshot_is_idempotent(monkeypatch):
    snapshot = {
        "SPY": {"date": "2026-07-07", "close": 620.0, "one_day_pct": 0.2, "sixty_day_pct": 8.0},
        "QQQ": {"date": "2026-07-07", "close": 560.0, "one_day_pct": 1.4, "sixty_day_pct": 12.0},
    }
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: snapshot)
    monkeypatch.setattr("investment_os.hard_source_collectors._download_stooq_snapshot", lambda _symbols: snapshot)

    first = collect_market_move_candidates(
        {"market_proxies": ["SPY", "QQQ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]
    unchanged = collect_market_move_candidates(
        {"market_proxies": ["SPY", "QQQ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]
    revised_snapshot = {symbol: dict(values) for symbol, values in snapshot.items()}
    revised_snapshot["QQQ"]["close"] = 561.25
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: revised_snapshot
    )
    revised = collect_market_move_candidates(
        {"market_proxies": ["SPY", "QQQ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]

    assert first.observed_value == unchanged.observed_value
    assert first.content_hash == unchanged.content_hash
    assert revised.observed_value != first.observed_value
    assert revised.content_hash != first.content_hash


def test_subthreshold_market_snapshot_does_not_claim_to_narrow_the_research_unknown(monkeypatch):
    snapshot = {
        "SPY": {"date": "2026-07-07", "close": 620.0, "one_day_pct": 0.2, "sixty_day_pct": 8.0},
    }
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: snapshot)
    monkeypatch.setattr("investment_os.hard_source_collectors._download_stooq_snapshot", lambda _symbols: snapshot)

    candidate = collect_market_move_candidates(
        {"market_proxies": ["SPY"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]

    assert candidate.thesis_impact == "unknown"


def test_conflicting_market_sources_are_explicitly_mixed(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._download_yfinance_snapshot",
        lambda _symbols: {"SPY": {"date": "2026-07-07", "close": 100.0, "one_day_pct": 1.0, "sixty_day_pct": 2.0}},
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._download_stooq_snapshot",
        lambda _symbols: {"SPY": {"date": "2026-07-07", "close": 80.0, "one_day_pct": 1.0, "sixty_day_pct": 2.0}},
    )
    candidate = collect_market_move_candidates(
        {"market_proxies": ["SPY"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]
    assert candidate.evidence_status == "mixed_sources"
    assert candidate.source_errors


def test_hard_source_rows_include_retrieval_and_body_contract_fields():
    candidates = collect_hard_source_candidates(
        WATCHLIST, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc)
    )
    assert candidates
    assert all(candidate.retrieved_at for candidate in candidates)
    assert all(candidate.body_read_status for candidate in candidates)


def test_sec_symbols_do_not_depend_on_hardcoded_group_names(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._safe_sec_recent",
        lambda: {"0": {"ticker": "ACME", "cik_str": "1234", "title": "Acme"}},
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._latest_sec_filing_for_cik",
        lambda _cik: {
            "form": "10-Q",
            "filing_date": "2026-07-07",
            "accession": "0001-02-03",
            "primary_doc": "acme.htm",
        },
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._http_text",
        lambda _url, timeout=10: "<html><body>synthetic filing body</body></html>",
    )

    candidates = collect_sec_recent_filing_candidates(
        {"custom_research": ["ACME", "HKCO"]},
        datetime(2026, 7, 8, tzinfo=timezone.utc),
        symbol_metadata={
            "ACME": {"market": "US", "sec_filings": True},
            "HKCO": {"market": "HK", "sec_filings": False},
        },
    )

    assert {candidate.tickers for candidate in candidates} == {"ACME"}
    assert any(candidate.evidence_status == "primary_body_read" for candidate in candidates)


def test_sec_collector_filters_irrelevant_forms(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._safe_sec_recent",
        lambda: {"0": {"ticker": "ACME", "cik_str": "1234", "title": "Acme"}},
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._latest_sec_filing_for_cik",
        lambda _cik: {
            "form": "S-1",
            "filing_date": "2026-07-07",
            "accession": "0001-02-03",
            "primary_doc": "acme.htm",
        },
    )

    assert collect_sec_recent_filing_candidates(
        {"custom_research": ["ACME"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    ) == []


def test_sec_body_candidate_retains_accession_url_and_hash(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._safe_sec_recent",
        lambda: {"0": {"ticker": "ACME", "cik_str": "1234", "title": "Acme"}},
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._latest_sec_filing_for_cik",
        lambda _cik: {
            "form": "8-K",
            "filing_date": "2026-07-07",
            "accession": "0001-02-03",
            "primary_doc": "acme.htm",
        },
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._http_text",
        lambda _url, timeout=10: "<html><body>synthetic filing body</body></html>",
    )

    body = next(
        candidate
        for candidate in collect_sec_recent_filing_candidates(
            {"research": ["ACME"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
        )
        if candidate.evidence_status == "primary_body_read"
    )

    assert body.accession_number == "0001-02-03"
    assert body.source_url.endswith("/acme.htm")
    assert body.content_hash.startswith("sha256:")
    assert body.cannot_prove
    assert body.retrieved_at == "2026-07-08T00:00:00+00:00"
    assert body.thesis_impact == "unknown_narrowed"


def test_sec_form4_metadata_does_not_block_newer_business_filing_body(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._safe_sec_recent",
        lambda: {"0": {"ticker": "ACME", "cik_str": "1234", "title": "Acme"}},
    )
    submissions = {
        "filings": {
            "recent": {
                "form": ["4", "8-K"],
                "filingDate": ["2026-07-08", "2026-07-07"],
                "accessionNumber": ["0001-04-01", "0001-08-01"],
                "primaryDocument": ["form4.xml", "event.htm"],
            }
        }
    }
    requested_urls = []
    monkeypatch.setattr("investment_os.hard_source_collectors._http_json", lambda _url, timeout=10: submissions)

    def fake_text(url: str, timeout=10):
        requested_urls.append(url)
        return "<html><body>8-K business filing body</body></html>"

    monkeypatch.setattr("investment_os.hard_source_collectors._http_text", fake_text)

    candidates = collect_sec_recent_filing_candidates(
        {"research": ["ACME"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )

    assert any("Form 4" in candidate.title or "is 4" in candidate.title for candidate in candidates)
    body = next(candidate for candidate in candidates if candidate.evidence_status == "primary_body_read")
    assert "8-K" in body.title
    assert body.accession_number == "0001-08-01"
    assert requested_urls and requested_urls[0].endswith("/event.htm")
    assert "form4.xml" not in json.dumps(body.to_row())
