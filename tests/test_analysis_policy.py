from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from investment_os.judgment_kernel import is_promotable
from investment_os.pipeline import FORBIDDEN_DECISION_WORDS, SymbolConfig, analyze_history, load_watchlist, render_report


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


def test_load_watchlist_accepts_grouped_public_sample():
    path = Path(__file__).resolve().parents[1] / "configs" / "watchlist.sample.yaml"

    _, symbols = load_watchlist(path)

    assert [item.symbol for item in symbols] == [
        "AAPL",
        "MSFT",
        "NVDA",
        "SPY",
        "QQQ",
        "IWM",
        "TLT",
        "UUP",
        "510300",
        "000300",
    ]
    assert symbols[0].notes.startswith("core_us:")
    assert symbols[0].source == "yahoo"
    assert symbols[-1].source == "china"


def test_load_watchlist_preserves_detailed_symbol_schema(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "symbols:\n  - symbol: AAPL\n    name: Apple\n    market: US\n    asset_class: equity\n",
        encoding="utf-8",
    )

    _, symbols = load_watchlist(path)

    assert symbols == [SymbolConfig(symbol="AAPL", name="Apple", market="US", asset_class="equity")]


def test_promotion_policy_fails_closed_for_targets_stale_metadata_and_missing_url():
    base = {
        "item_id": "company:ACME:event",
        "lane": "company_events",
        "title": "Verified event",
        "summary": "A primary document changed.",
        "source": "SEC filing body",
        "source_type": "primary_filing_body_read",
        "source_url": "https://www.sec.gov/example.htm",
        "as_of_date": "2026-07-03",
        "retrieved_at": "2026-07-05T08:00:00+00:00",
        "freshness_status": "current",
        "freshness_threshold_days": 3,
        "body_read_status": "read",
        "content_hash": "sha256:abc",
        "evidence_status": "primary_body_read",
        "counter_explanation": "The filing could be routine rather than material.",
        "next_primary_source": "The next filing and earnings call.",
        "kill_signal": "Block the claim if the filing is amended.",
        "cannot_prove": "One filing cannot prove a durable trend.",
    }
    assert is_promotable(base)
    for updates in (
        {"evidence_status": "source_target_only"},
        {"evidence_status": "stale"},
        {"evidence_status": "primary_metadata_only"},
        {"source_url": ""},
        {"content_hash": ""},
    ):
        assert not is_promotable({**base, **updates})


def test_promotion_policy_requires_the_complete_explicit_evidence_contract():
    base = {
        "item_id": "macro:DGS10",
        "lane": "macro_regime",
        "title": "Fresh official observation",
        "summary": "The official series published a new value.",
        "source": "FRED",
        "source_type": "primary_macro_fred_live",
        "source_url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
        "as_of_date": "2026-07-03",
        "retrieved_at": "2026-07-05T08:00:00+00:00",
        "freshness_status": "current",
        "freshness_threshold_days": 3,
        "content_hash": "sha256:fred-value",
        "evidence_status": "single_source_data",
        "counter_explanation": "One series can conflict with adjacent official data.",
        "next_primary_source": "Adjacent official series.",
        "kill_signal": "Treat as background if revised or stale.",
        "cannot_prove": "One observation cannot prove causality.",
    }
    assert is_promotable(base)

    required = (
        "retrieved_at",
        "freshness_status",
        "freshness_threshold_days",
        "content_hash",
        "counter_explanation",
        "next_primary_source",
        "kill_signal",
        "cannot_prove",
        "source_type",
        "source_url",
    )
    for field in required:
        assert not is_promotable({**base, field: ""}), field
    for updates in (
        {"retrieved_at": "not-a-timestamp"},
        {"retrieved_at": "2026-07-05T08:00:00"},
        {"freshness_status": "unknown"},
        {"freshness_threshold_days": 0},
        {"content_hash": "not-a-fingerprint"},
        {"source_url": "not-a-url"},
        {"as_of_date": "2026-07-01"},
        {"as_of_date": "not-a-date"},
    ):
        assert not is_promotable({**base, **updates})
