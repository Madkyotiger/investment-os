"""A run reviews a limited number of due questions; the rest stay open and are reported, not required."""
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from investment_os import radar_store
from investment_os.upstream_radar import evaluate_packet, load_objective, write_outputs
from investment_os.upstream_radar_preflight import build_digest, build_preflight
from test_upstream_radar_repair import _packet, _qualifying_item

CONFIG = Path("configs/upstream_radar.sample.yaml")
# The fixture sources are captured once, so the three runs sit inside one capture window.
DAY2 = "2026-09-08T08:00:00+08:00"
DAY3 = "2026-09-08T09:00:00+08:00"


def _objective(budget: int | None):
    return replace(load_objective(CONFIG), followup_review_budget=budget)


def _seed(tmp_path: Path):
    """Three open questions; `q:reviewed` (impact 5) has been reviewed once and is due again at the third run."""
    objective = _objective(2)
    db = tmp_path / "index.sqlite"
    conn = radar_store.open_db(db)
    first = _packet(tmp_path, [
        _qualifying_item("q:reviewed", impact_score=5),
        _qualifying_item("q:new-low", impact_score=4),
        _qualifying_item("q:new-high", impact_score=5),
    ])
    radar_store.ingest_run(conn, first, evaluate_packet(first, objective, run_dir=tmp_path), tmp_path)
    second = _packet(tmp_path, [])
    second.update(run_id="day2", as_of=DAY2)
    second["followup_updates"] = [dict(
        tracking_key="q:reviewed", status="open", next_check_at="2026-09-08T08:30:00+08:00",
        reason="本轮来源没有改变判断。", source_ids=["cov-0"],
    )]
    radar_store.ingest_run(conn, second, evaluate_packet(second, objective, run_dir=tmp_path), tmp_path)
    return objective, db, conn


def _review(key: str) -> dict:
    return dict(tracking_key=key, status="open", next_check_at="2026-09-14T08:00:00+08:00", reason="本轮来源没有改变判断。", source_ids=["cov-0"])


def test_first_looks_come_before_rechecks_and_the_rest_is_deferred(tmp_path: Path):
    _, _, conn = _seed(tmp_path)
    now = datetime.fromisoformat(DAY3)

    rows = {row["tracking_key"]: row for row in radar_store.readback_followups(conn, now, review_budget=2)}

    assert {key for key, row in rows.items() if row["required"]} == {"q:new-high", "q:new-low"}
    assert rows["q:reviewed"]["due"] and rows["q:reviewed"]["deferred"] and rows["q:reviewed"]["review_count"] == 1
    # With one slot, the higher-impact unreviewed question takes it.
    one = {row["tracking_key"] for row in radar_store.readback_followups(conn, now, review_budget=1) if row["required"]}
    assert one == {"q:new-high"}
    # No budget: every due question is still required, as before.
    assert all(row["required"] and not row["deferred"] for row in radar_store.readback_followups(conn, now))


def test_publishing_run_reports_both_lists(tmp_path: Path):
    objective, db, _ = _seed(tmp_path)
    packet = _packet(tmp_path, [_qualifying_item("fresh:item")])
    packet.update(run_id="day3", as_of=DAY3)
    packet["followup_updates"] = [_review("q:new-high")]

    paths = write_outputs(evaluate_packet(packet, objective, run_dir=tmp_path), objective, tmp_path / "output",
                          packet=packet, run_dir=tmp_path, db_path=db)

    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    assert receipt["outcome"] == "push"
    assert receipt["unreviewed_due_followups"] == ["q:new-low"]
    assert receipt["deferred_due_followups"] == ["q:reviewed"]
    assert receipt["followup_review_budget"] == 2


def test_silent_run_is_held_only_by_its_own_review_list(tmp_path: Path):
    objective, db, conn = _seed(tmp_path)
    quiet = _packet(tmp_path, [])
    quiet.update(run_id="day3", as_of=DAY3)
    quiet["followup_updates"] = [_review("q:new-high")]
    with pytest.raises(ValueError, match="due followups not reviewed: q:new-low"):
        write_outputs(evaluate_packet(quiet, objective, run_dir=tmp_path), objective, tmp_path / "output",
                      packet=quiet, run_dir=tmp_path, db_path=db)

    quiet["followup_updates"].append(_review("q:new-low"))
    result = evaluate_packet(quiet, objective, run_dir=tmp_path)
    paths = write_outputs(result, objective, tmp_path / "output", packet=quiet, run_dir=tmp_path, db_path=db)
    assert paths["delivery_final"].read_text(encoding="utf-8") == "[SILENT]"

    # The same run evaluated again (final text attached) is judged against the same list,
    # not against whatever moved up after its own reviews were stored.
    paths = write_outputs(result, objective, tmp_path / "output", packet=quiet, run_dir=tmp_path, db_path=db)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    assert receipt["status"] == "pass" and receipt["unreviewed_due_followups"] == []
    assert receipt["deferred_due_followups"] == ["q:reviewed"]


def test_a_deferred_question_can_still_be_reviewed_when_news_touches_it(tmp_path: Path):
    objective, db, conn = _seed(tmp_path)
    packet = _packet(tmp_path, [_qualifying_item("fresh:item")])
    packet.update(run_id="day3", as_of=DAY3)
    packet["followup_updates"] = [dict(tracking_key="q:reviewed", status="superseded", next_check_at=None,
                                       reason="本轮来源推翻了原判断。", source_ids=["cov-0"])]

    paths = write_outputs(evaluate_packet(packet, objective, run_dir=tmp_path), objective, tmp_path / "output",
                          packet=packet, run_dir=tmp_path, db_path=db)

    assert json.loads(paths["receipt"].read_text(encoding="utf-8"))["deferred_due_followups"] == []
    rows = {row["tracking_key"]: row for row in radar_store.readback_followups(conn, datetime.fromisoformat(DAY3), include_closed=True)}
    assert rows["q:reviewed"]["status"] == "superseded"


def test_preflight_hands_over_the_review_list_and_names_the_rest(tmp_path: Path):
    objective, db, _ = _seed(tmp_path)
    manifest = build_preflight(objective, datetime.fromisoformat(DAY3), None, db_path=db)
    digest = build_digest(manifest, tmp_path / "seen-state.json", "0" * 64)

    assert [row["tracking_key"] for row in digest["due_followups"]] == ["q:new-high", "q:new-low"]
    assert digest["due_deferred"] == [{"tracking_key": "q:reviewed", "title": "事件 q:reviewed", "impact_score": 5, "days_open": 0, "review_count": 1}]
    assert "上限 2 条" in digest["followup_rule"]
    # The full manifest keeps the deferred question's judgment for lookup by tracking_key.
    assert manifest["deferred_followups"][0]["judgment"]["falsifier"]

    unbudgeted = build_preflight(_objective(None), datetime.fromisoformat(DAY3), None, db_path=db)
    plain = build_digest(unbudgeted, tmp_path / "seen-state.json", "0" * 64)
    assert len(plain["due_followups"]) == 3 and plain["due_deferred"] == [] and plain["followup_rule"] is None


@pytest.mark.parametrize("value", [0, -1, "12", True, 1.5])
def test_budget_must_be_a_positive_integer(tmp_path: Path, value):
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    raw["followup_review_budget"] = value
    path = tmp_path / "radar.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ValueError, match="followup_review_budget"):
        load_objective(path)
