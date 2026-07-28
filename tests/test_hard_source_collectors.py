from datetime import datetime, timezone
from pathlib import Path

from investment_os.hard_source_collectors import (
    collect_fred_yield_candidates,
    collect_hard_source_candidates,
    collect_market_move_candidates,
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
