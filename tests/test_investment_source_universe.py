from pathlib import Path

import yaml


SOURCE_UNIVERSE_PATH = Path("configs/investment_source_universe.yaml")


def test_source_universe_is_not_ai_only():
    config = yaml.safe_load(SOURCE_UNIVERSE_PATH.read_text(encoding="utf-8"))
    lanes = config["lanes"]

    assert len(lanes) >= 6
    assert "sector_theme_discovery" in lanes
    assert "macro_regime" in lanes
    assert "company_events" in lanes
    assert "market_action" in lanes
    assert "portfolio_watchlist" in lanes
    assert "AI infrastructure is a pilot topic" in SOURCE_UNIVERSE_PATH.read_text(encoding="utf-8")


def test_daily_selection_ranks_by_decision_usefulness_not_fixed_theme():
    config = yaml.safe_load(SOURCE_UNIVERSE_PATH.read_text(encoding="utf-8"))

    rank_by = config["daily_selection"]["rank_by"]
    exclude = config["daily_selection"]["exclude"]

    assert rank_by[0] == "decision_usefulness"
    assert "evidence_change" in rank_by
    assert "portfolio_relevance" in rank_by
    assert "repeated_theme_without_new_evidence" in exclude
    assert "trade_instruction" in exclude
