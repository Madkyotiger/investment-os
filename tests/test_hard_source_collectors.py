import json
import types
import builtins
from datetime import date, datetime, timezone

from investment_os.cxo_intelligence import _zh
from pathlib import Path

import pytest

from investment_os.evidence_contract import normalize_evidence_status
from investment_os.hard_source_collectors import (
    HardSourceCandidate,
    _download_yfinance_snapshot,
    _session_is_complete,
    get_last_source_errors,
    collect_fred_yield_candidates,
    collect_hard_source_candidates,
    collect_market_move_candidates,
    collect_sec_recent_filing_candidates,
    write_hard_source_candidates,
)
from investment_os.judgment_kernel import classify_change, is_promotable

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
    assert candidates[0].thesis_impact == "unknown"
    assert not classify_change(
        None,
        candidates[0].to_row(),
        datetime(2026, 7, 8, tzinfo=timezone.utc),
    ).meaningful_change
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
            "SPY": {"date": "2026-07-07", "close": 620.0, "one_day_pct": 0.2, "sixty_day_pct": 8.0, "daily_vol_pct": 0.8},
            "QQQ": {"date": "2026-07-07", "close": 560.0, "one_day_pct": 1.4, "sixty_day_pct": 12.0, "daily_vol_pct": 0.6},
        }

    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", fake_snapshot)
    candidates = collect_market_move_candidates({"market_proxies": ["SPY", "QQQ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc))

    assert candidates[0].source_type == "market_proxy_prices_live"
    assert candidates[0].confidence == "market_data_probable"
    assert candidates[0].evidence_status == "single_source_data"
    assert candidates[0].tickers == "SPY,QQQ"
    assert candidates[0].title == "QQQ 单日 1.4%，约为自身近60日日波动的 2.3 倍"
    assert "单源" in candidates[0].summary
    assert candidates[0].retrieved_at == "2026-07-08T00:00:00+00:00"
    assert candidates[0].thesis_impact == "unknown_narrowed"
    observed = json.loads(candidates[0].observed_value)
    assert set(observed) == {"primary_yfinance"}
    assert candidates[0].content_hash.startswith("sha256:")
    assert candidates[0].freshness_threshold_days == 5


def test_market_daily_collects_us_and_hk_watchlist_symbols_not_only_proxies(monkeypatch):
    captured: list[str] = []

    def fake_primary(symbols: list[str]):
        captured.extend(symbols)
        return {
            symbol: {"date": "2026-07-07", "close": 100.0, "one_day_pct": 1.0, "sixty_day_pct": 2.0}
            for symbol in symbols
        }

    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", fake_primary)

    candidate = collect_market_move_candidates(
        {
            "core_us": ["NVDA"],
            "core_hk": ["0700.HK"],
            "market_proxies": ["SPY"],
            "china_parallel": ["510300"],
        },
        datetime(2026, 7, 8, tzinfo=timezone.utc),
        symbol_metadata={
            "NVDA": {"market": "US", "asset_type": "equity"},
            "0700.HK": {"market": "HK", "asset_type": "equity"},
            "SPY": {"market": "US", "asset_type": "etf"},
            "510300": {"market": "CN", "asset_type": "etf"},
        },
    )[0]

    assert captured == ["SPY", "NVDA", "0700.HK"]
    assert candidate.tickers == "SPY,NVDA,0700.HK"
    assert "510300" not in candidate.tickers
    assert candidate.title == "市场观察名单单日波动均在各自常态范围内"


def test_market_move_candidate_uses_configured_snapshot_freshness(monkeypatch):
    snapshot = {
        "SPY": {"date": "2026-06-01", "close": 620.0, "one_day_pct": 1.2, "sixty_day_pct": 8.0},
    }
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: snapshot)

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

    candidate = collect_market_move_candidates(
        {"market_proxies": ["SPY"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]

    assert candidate.thesis_impact == "unknown"


def test_market_symbol_missing_from_the_quote_source_is_named_to_the_reader(monkeypatch):
    primary = {
        "SPY": {"date": "2026-07-07", "close": 620.0, "one_day_pct": 1.2, "sixty_day_pct": 8.0},
    }
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: primary)

    candidate = collect_market_move_candidates(
        {"market_proxies": ["SPY", "QQQ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )[0]

    assert candidate.confidence == "market_data_probable"
    assert candidate.evidence_status == "single_source_data"
    assert candidate.tickers == "SPY"
    assert candidate.summary.startswith("主行情缺少 QQQ。")


def test_hard_source_rows_include_retrieval_and_body_contract_fields():
    candidates = collect_hard_source_candidates(
        WATCHLIST, generated_at=datetime(2026, 7, 8, tzinfo=timezone.utc)
    )
    assert candidates
    assert all(candidate.retrieved_at for candidate in candidates)
    assert all(candidate.body_read_status for candidate in candidates)


def test_retrieval_source_type_cannot_self_upgrade_to_body_read():
    status = normalize_evidence_status(
        {
            "source_type": "primary_filing_body_retrieved",
            "evidence_status": "primary_body_read",
            "body_read_status": "read",
            "source_url": "https://www.sec.gov/Archives/example.htm",
            "content_hash": "sha256:retrieved-only",
            "freshness_status": "current",
        }
    )

    assert status == "primary_body_retrieved"

    candidate = HardSourceCandidate(
        item_id="sec:retrieval-only",
        lane="company_events",
        title="Retrieved filing",
        summary="The filing was downloaded but not read.",
        source="SEC",
        source_type="primary_filing_body_retrieved",
        as_of_date="2026-07-08",
        source_url="https://www.sec.gov/Archives/example.htm",
        content_hash="sha256:retrieved-only",
        body_read_status="read",
        evidence_status="primary_body_read",
    )
    assert candidate.body_read_status == "retrieved"
    assert candidate.evidence_status == "primary_body_retrieved"
    assert not is_promotable(candidate.to_row())


def test_body_read_status_requires_a_read_specific_source_type():
    status = normalize_evidence_status(
        {
            "source_type": "primary_filing_body_unverified",
            "evidence_status": "primary_body_read",
            "body_read_status": "read",
            "source_url": "https://www.sec.gov/Archives/example.htm",
            "as_of_date": "2026-07-08",
            "content_hash": "sha256:unverified",
            "freshness_status": "current",
        }
    )

    assert status == "primary_metadata_only"


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
    body = next(candidate for candidate in candidates if candidate.evidence_status == "primary_body_retrieved")
    assert body.body_read_status == "retrieved"
    assert not is_promotable(body.to_row())


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


def test_sec_body_retrieval_retains_accession_url_and_hash_without_claiming_read(monkeypatch):
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
        if candidate.evidence_status == "primary_body_retrieved"
    )

    assert body.accession_number == "0001-02-03"
    assert body.source_url.endswith("/acme.htm")
    assert body.content_hash.startswith("sha256:")
    assert body.cannot_prove
    assert body.retrieved_at == "2026-07-08T00:00:00+00:00"
    assert body.body_read_status == "retrieved"
    assert body.thesis_impact == "unknown"
    assert not is_promotable(body.to_row())


def test_old_sec_metadata_and_body_are_stale_and_nonpromotable(monkeypatch):
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._safe_sec_recent",
        lambda: {"0": {"ticker": "ACME", "cik_str": "1234", "title": "Acme"}},
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._latest_sec_filing_for_cik",
        lambda _cik: {
            "form": "10-Q",
            "filing_date": "2026-06-01",
            "accession": "0001-02-03",
            "primary_doc": "acme.htm",
        },
    )
    monkeypatch.setattr(
        "investment_os.hard_source_collectors._http_text",
        lambda _url, timeout=10: "<html><body>old filing body</body></html>",
    )

    candidates = collect_sec_recent_filing_candidates(
        {"research": ["ACME"]}, datetime(2026, 7, 8, tzinfo=timezone.utc)
    )

    assert len(candidates) == 2
    assert all(candidate.freshness_status == "stale" for candidate in candidates)
    assert all(candidate.evidence_status == "stale" for candidate in candidates)
    assert all(not is_promotable(candidate.to_row()) for candidate in candidates)


def test_yfinance_failures_are_recorded_as_structured_secret_safe_market_errors(monkeypatch):
    import investment_os.hard_source_collectors as collectors

    collectors._LAST_SOURCE_ERRORS.clear()
    monkeypatch.setitem(
        __import__("sys").modules,
        "yfinance",
        types.SimpleNamespace(download=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("token=secret"))),
    )

    assert _download_yfinance_snapshot(["SPY"]) == {}
    error = get_last_source_errors()[-1]
    assert error == {
        "source": "yfinance",
        "lane": "market_action",
        "code": "download_error",
        "message": "yfinance market snapshot download failed",
        "source_url": "https://query1.finance.yahoo.com/",
        "transient": True,
    }
    assert "secret" not in json.dumps(error)


@pytest.mark.parametrize(
    ("raised", "code", "message"),
    [
        (ImportError("not installed"), "unavailable", "yfinance market adapter is unavailable"),
        (RuntimeError("token=secret"), "adapter_error", "yfinance market adapter failed to initialize"),
    ],
)
def test_yfinance_import_and_adapter_failures_are_structured(monkeypatch, raised, code, message):
    import investment_os.hard_source_collectors as collectors

    collectors._LAST_SOURCE_ERRORS.clear()
    original_import = builtins.__import__

    def fail_yfinance(name, *args, **kwargs):
        if name == "yfinance":
            raise raised
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_yfinance)

    assert _download_yfinance_snapshot(["SPY"]) == {}
    assert get_last_source_errors()[-1] == {
        "source": "yfinance",
        "lane": "market_action",
        "code": code,
        "message": message,
        "source_url": "https://query1.finance.yahoo.com/",
        "transient": False,
    }


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
    body = next(candidate for candidate in candidates if candidate.evidence_status == "primary_body_retrieved")
    assert "8-K" in body.title
    assert body.accession_number == "0001-08-01"
    assert requested_urls and requested_urls[0].endswith("/event.htm")
    assert "form4.xml" not in json.dumps(body.to_row())


def test_market_move_is_judged_against_each_symbols_own_volatility(monkeypatch):
    # NVDA moves 3% on an ordinary day for NVDA; TLT moves 1.3% on an unusual day for TLT.
    snapshot = {
        "NVDA": {"date": "2026-07-07", "close": 170.0, "one_day_pct": -3.0, "sixty_day_pct": 5.0, "daily_vol_pct": 2.6},
        "TLT": {"date": "2026-07-07", "close": 81.0, "one_day_pct": -1.3, "sixty_day_pct": 0.5, "daily_vol_pct": 0.6},
        "SPY": {"date": "2026-07-07", "close": 620.0, "one_day_pct": 0.4, "sixty_day_pct": 8.0, "daily_vol_pct": None},
    }
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: snapshot)
    groups = {"market_proxies": ["NVDA", "TLT", "SPY"]}

    candidate = collect_market_move_candidates(groups, datetime(2026, 7, 8, tzinfo=timezone.utc))[0]

    assert candidate.title == "TLT 单日 -1.3%，约为自身近60日日波动的 2.2 倍"
    assert _zh(candidate.title) == candidate.title  # the reader-text pass must not strip words from it
    assert candidate.thesis_impact == "unknown_narrowed"
    assert candidate.summary.startswith("TLT 收盘 81.0，单日 -1.3%（自身常态的 2.2 倍）")

    snapshot["TLT"]["one_day_pct"] = -0.9
    quiet = collect_market_move_candidates(groups, datetime(2026, 7, 8, tzinfo=timezone.utc))[0]

    assert quiet.title == "市场观察名单单日波动均在各自常态范围内"
    assert quiet.thesis_impact == "unknown"
    assert quiet.evidence_change == 2


def test_daily_bar_counts_as_a_close_only_after_its_exchange_has_closed():
    hong_kong_afternoon = datetime(2026, 11, 11, 5, 21, tzinfo=timezone.utc)

    assert not _session_is_complete("0700.HK", date(2026, 11, 11), hong_kong_afternoon)
    assert _session_is_complete("0700.HK", date(2026, 11, 10), hong_kong_afternoon)
    assert _session_is_complete("NVDA", date(2026, 11, 10), hong_kong_afternoon)
    assert not _session_is_complete("NVDA", date(2026, 11, 11), datetime(2026, 11, 11, 20, 30, tzinfo=timezone.utc))
    assert _session_is_complete("NVDA", date(2026, 11, 11), datetime(2026, 11, 11, 21, 15, tzinfo=timezone.utc))


def test_yfinance_snapshot_ignores_a_bar_whose_session_is_still_open(monkeypatch):
    import pandas as pd

    # 2099-01-05 has not closed yet on any clock this test runs on; every earlier bar has.
    days = pd.bdate_range(end="2099-01-05", periods=30)
    closes = [100.0 + (index % 3) for index in range(29)] + [150.0]
    frame = pd.concat({"Close": pd.DataFrame({"0700.HK": closes}, index=days)}, axis=1)
    monkeypatch.setitem(
        __import__("sys").modules, "yfinance", types.SimpleNamespace(download=lambda *_args, **_kwargs: frame)
    )

    snapshot = _download_yfinance_snapshot(["0700.HK"])["0700.HK"]

    assert snapshot["date"] == str(days[-2].date())
    assert snapshot["close"] == closes[-2]
    assert snapshot["daily_vol_pct"] is not None and snapshot["daily_vol_pct"] > 0


def test_sec_checks_every_listed_symbol_and_names_the_ones_it_cannot_resolve(monkeypatch):
    import investment_os.hard_source_collectors as collectors

    tickers = [f"AA{chr(65 + index)}" for index in range(12)]
    sec_map = {str(index): {"ticker": ticker, "cik_str": 1000 + index} for index, ticker in enumerate(tickers)}
    asked: list[str] = []
    monkeypatch.setattr(collectors, "_latest_sec_filing_for_cik", lambda cik: asked.append(cik))
    collectors._LAST_SOURCE_ERRORS.clear()

    collect_sec_recent_filing_candidates(
        {"core": tickers + ["ZZZZ"]}, datetime(2026, 7, 8, tzinfo=timezone.utc), sec_map=sec_map
    )

    assert [cik for cik in asked if cik] == [str(1000 + index) for index in range(12)]
    gap = get_last_source_errors()[-1]
    assert gap["code"] == "not_checked"
    assert gap["message"].endswith("filings not checked: ZZZZ")

