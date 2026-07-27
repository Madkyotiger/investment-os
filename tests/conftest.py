from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def block_network_collectors(monkeypatch):
    """Keep the public test suite deterministic and offline."""
    monkeypatch.setattr("investment_os.hard_source_collectors._safe_sec_recent", lambda: {})
    monkeypatch.setattr("investment_os.hard_source_collectors._fred_latest", lambda _series_id: None)
    monkeypatch.setattr("investment_os.hard_source_collectors._download_yfinance_snapshot", lambda _symbols: {})
    monkeypatch.setattr("investment_os.hard_source_collectors._download_stooq_snapshot", lambda _symbols: {})
