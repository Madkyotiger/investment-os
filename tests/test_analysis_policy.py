from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from investment_os.pipeline import FORBIDDEN_DECISION_WORDS, SymbolConfig, analyze_history, render_report


def fake_history(values: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-07-03", periods=len(values))
    return pd.DataFrame({"Close": values}, index=dates)


def test_suggestions_are_research_actions_not_trade_decisions():
    cfg = SymbolConfig(symbol="TEST", name="Test Asset", market="US", asset_class="equity")
    values = list(np.linspace(100, 130, 90))
    metrics = analyze_history(cfg, fake_history(values), generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    suggestion = metrics.research_suggestion.lower()
    for word in FORBIDDEN_DECISION_WORDS:
        assert word.lower() not in suggestion
    assert metrics.research_priority in {"priority_research", "standard_monitoring", "risk_review", "watch_with_triggers"}


def test_missing_data_degrades_to_data_check_first():
    cfg = SymbolConfig(symbol="MISSING", name="Missing Asset", market="CN", asset_class="equity")
    metrics = analyze_history(cfg, pd.DataFrame(), generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert metrics.data_quality == "missing"
    assert metrics.research_priority == "data_check_first"
    assert "补充替代数据源" in metrics.research_suggestion


def test_render_report_contains_disclaimer_and_no_trade_phrases():
    cfg = SymbolConfig(symbol="TEST", name="Test Asset", market="US", asset_class="equity")
    metrics = [analyze_history(cfg, fake_history(list(np.linspace(100, 110, 90))), generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))]
    report = render_report({"profile_name": "test"}, metrics, generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert "不构成投资建议" in report
    assert "research suggestions only" in report
    forbidden_phrases = ["建议买入", "建议卖出", "建议持有", "建议加仓", "建议减仓"]
    for phrase in forbidden_phrases:
        assert phrase not in report
