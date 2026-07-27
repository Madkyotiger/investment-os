from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .judgment_kernel import (
    classify_change,
    enrich_candidate_row,
    infer_topic_key,
    select_representative_rows,
)


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass
class TopicState:
    item_id: str
    lane: str
    title: str
    last_summary: str
    current_thesis: str
    open_questions: str
    watch_signals: str
    kill_signal: str
    last_score: int
    last_seen: str
    update_count: int = 1
    thesis_key: str = ""
    research_question: str = ""
    thesis_impact: str = "unknown"
    counter_explanation: str = ""
    next_primary_source: str = ""
    evidence_status: str = "unknown"
    geography: str = ""
    source_url: str = ""
    as_of_date: str = ""
    cannot_prove: str = ""
    evidence_fingerprint: str = ""
    is_active: bool = True


@dataclass
class TopicChange:
    item_id: str
    lane: str
    title: str
    change_type: str
    previous_summary: str
    latest_summary: str
    previous_score: int
    latest_score: int
    changed_since_last_push: bool
    next_check: str
    kill_signal: str
    thesis_key: str = ""
    research_question: str = ""
    thesis_impact: str = "unknown"
    counter_explanation: str = ""
    next_primary_source: str = ""
    evidence_status: str = "unknown"
    geography: str = ""
    source_url: str = ""
    as_of_date: str = ""
    cannot_prove: str = ""
    change_reason: str = ""

    def to_row(self) -> dict[str, str | int | bool]:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def parse_generated_at(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=LOCAL_TIMEZONE)


def _read_candidate_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _load_state(path: Path) -> dict[str, TopicState]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    migrated: dict[str, TopicState] = {}
    for storage_key, data in raw.items():
        state = TopicState(**data)
        if not state.thesis_key:
            state.thesis_key = infer_topic_key(
                {
                    "item_id": state.item_id or storage_key,
                    "lane": state.lane,
                    "title": state.title,
                }
            )
        key = state.thesis_key or storage_key
        existing = migrated.get(key)
        if existing is None or state.last_score > existing.last_score:
            migrated[key] = state
    return migrated


def _score(row: dict[str, object]) -> int:
    if row.get("cxo_total_score"):
        return int(float(str(row["cxo_total_score"])))
    if row.get("total_score"):
        return int(float(str(row["total_score"])))
    fields = ["source_authority", "freshness", "evidence_change", "magnitude", "novelty", "decision_usefulness", "portfolio_relevance"]
    return sum(int(float(str(row.get(field) or 0))) for field in fields)


def _short(text: object, limit: int = 240) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[:limit].rstrip() + "…"


def update_topic_state(
    candidates_csv_path: Path,
    state_path: Path,
    out_dir: Path,
    generated_at: datetime | None = None,
) -> tuple[list[TopicChange], Path, Path]:
    generated_at = generated_at or _now()
    seen_at = generated_at.astimezone(LOCAL_TIMEZONE).date().isoformat()
    previous_state = _load_state(state_path)
    raw_rows = _read_candidate_rows(candidates_csv_path)
    raw_item_ids = {str(row.get("item_id", "")) for row in raw_rows}
    rows = select_representative_rows(raw_rows)
    previous_by_item_id = {state.item_id: (key, state) for key, state in previous_state.items()}
    consumed_previous_keys: set[str] = set()
    out_dir.mkdir(parents=True, exist_ok=True)

    changes: list[TopicChange] = []
    new_state: dict[str, TopicState] = {}
    for raw_row in rows:
        row = enrich_candidate_row(raw_row)
        thesis_key = str(row["thesis_key"])
        previous_key = thesis_key
        previous = previous_state.get(thesis_key)
        if previous is None and str(row.get("item_id", "")) in previous_by_item_id:
            previous_key, previous = previous_by_item_id[str(row.get("item_id", ""))]
        if previous is not None:
            consumed_previous_keys.add(previous_key)
        score = _score(row)
        latest_summary = _short(row.get("summary", ""))
        assessment_row = dict(row)
        assessment_row["summary"] = latest_summary
        assessment = classify_change(asdict(previous) if previous else None, assessment_row, generated_at)
        changes.append(
            TopicChange(
                item_id=str(row.get("item_id", "")),
                lane=str(row.get("lane", "")),
                title=str(row.get("title", "")),
                change_type=assessment.change_type,
                previous_summary=previous.last_summary if previous else "",
                latest_summary=latest_summary,
                previous_score=previous.last_score if previous else 0,
                latest_score=score,
                changed_since_last_push=assessment.meaningful_change,
                next_check=str(row.get("next_check", "")),
                kill_signal=str(row.get("kill_signal", "")),
                thesis_key=thesis_key,
                research_question=str(row["research_question"]),
                thesis_impact=str(row["thesis_impact"]),
                counter_explanation=str(row["counter_explanation"]),
                next_primary_source=str(row["next_primary_source"]),
                evidence_status=str(row["evidence_status"]),
                geography=str(row["geography"]),
                source_url=str(row.get("source_url", "")),
                as_of_date=str(row.get("as_of_date", "")),
                cannot_prove=str(row.get("cannot_prove", "")),
                change_reason=assessment.reason,
            )
        )
        if previous is not None and assessment.change_type in {
            "metadata_only",
            "background_only",
            "evidence_without_impact",
        }:
            new_state[thesis_key] = replace(previous, last_seen=seen_at, is_active=True)
            continue
        new_state[thesis_key] = TopicState(
            item_id=str(row.get("item_id", "")),
            lane=str(row.get("lane", "")),
            title=str(row.get("title", "")),
            last_summary=latest_summary,
            current_thesis=str(row["research_question"]),
            open_questions=str(row["next_primary_source"]),
            watch_signals=str(row.get("themes", "")),
            kill_signal=str(row.get("kill_signal", "")),
            last_score=score,
            last_seen=seen_at,
            update_count=(previous.update_count + 1) if previous else 1,
            thesis_key=thesis_key,
            research_question=str(row["research_question"]),
            thesis_impact=str(row["thesis_impact"]),
            counter_explanation=str(row["counter_explanation"]),
            next_primary_source=str(row["next_primary_source"]),
            evidence_status=str(row["evidence_status"]),
            geography=str(row["geography"]),
            source_url=str(row.get("source_url", "")),
            as_of_date=str(row.get("as_of_date", "")),
            cannot_prove=str(row.get("cannot_prove", "")),
            evidence_fingerprint=assessment.evidence_fingerprint,
        )

    # Falling out of a ranked pool is a ranking event, not a thesis change.
    # Retain inactive state so the same evidence cannot re-enter as a new question.
    # Legacy item-id keyed states that still exist in the current raw pool are migration residue.
    for previous_key, previous in previous_state.items():
        if previous_key in consumed_previous_keys or previous_key in new_state:
            continue
        if previous.item_id in raw_item_ids:
            new_state.setdefault(previous_key, previous)
            continue
        new_state[previous_key] = replace(previous, is_active=False)
        if not previous.is_active:
            continue
        changes.append(
            TopicChange(
                item_id=previous.item_id,
                lane=previous.lane,
                title=previous.title,
                change_type="ranking_only",
                previous_summary=previous.last_summary,
                latest_summary="",
                previous_score=previous.last_score,
                latest_score=0,
                changed_since_last_push=False,
                next_check=previous.open_questions,
                kill_signal=previous.kill_signal,
                thesis_key=previous.thesis_key or previous_key,
                research_question=previous.research_question or previous.current_thesis,
                thesis_impact=previous.thesis_impact,
                counter_explanation=previous.counter_explanation,
                next_primary_source=previous.next_primary_source,
                evidence_status=previous.evidence_status,
                geography=previous.geography,
                source_url=previous.source_url,
                as_of_date=previous.as_of_date,
                cannot_prove=previous.cannot_prove,
                change_reason="候选掉出排序池，但没有新证据证明判断变化",
            )
        )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({key: asdict(value) for key, value in sorted(new_state.items())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    changes_json = out_dir / "topic_changes.json"
    changes_csv = out_dir / "topic_changes.csv"
    rows_out = [change.to_row() for change in changes]
    changes_json.write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
    if rows_out:
        with changes_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
    else:
        changes_csv.write_text("", encoding="utf-8")
    return changes, changes_json, changes_csv


def _digest_title(title: str) -> str:
    replacements = {
        "Memory/passives look like the next AI infrastructure bottleneck to verify": "内存和被动件的瓶颈假设",
        "Data-center power and cooling are moving from engineering constraint to market variable": "数据中心电力和散热约束",
        "Treasury yield curve should anchor duration-sensitive equity interpretation": "美债利率对长久期资产的影响",
        "FRED yield curve snapshot": "美债收益率变化",
        "NVDA filing body changes the margin question": "NVDA 利润率质量",
    }
    value = title
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def render_change_digest(changes: list[TopicChange], max_items: int = 5) -> str:
    changed = [change for change in changes if change.changed_since_last_push]
    if not changed:
        return "今天没有足够新的主题变化；沿用上次判断，等待新的财报、价格或正式来源触发。"
    lines: list[str] = []
    for change in changed[:max_items]:
        title = _digest_title(change.title)
        next_source = change.next_primary_source.rstrip("。.")
        if change.change_type == "new_question":
            lines.append(f"新增研究问题：{title}；接着看 {next_source}。")
        elif change.change_type == "hypothesis_strengthened":
            lines.append(f"判断强化：{title}；接着看 {next_source}。")
        elif change.change_type == "hypothesis_weakened":
            lines.append(f"判断削弱：{title}；接着看 {next_source}。")
        elif change.change_type == "unknown_narrowed":
            lines.append(f"关键未知缩小：{title}；接着看 {next_source}。")
        elif change.change_type == "unknown_expanded":
            lines.append(f"关键未知扩大：{title}；接着看 {next_source}。")
    return "\n".join(lines) or "今天没有足够新的主题变化；沿用上次判断，等待新的财报、价格或正式来源触发。"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track evidence-backed research-question changes between intelligence runs.")
    parser.add_argument("--candidates", type=Path, default=Path("reports/source-universe/source_universe_candidates.csv"))
    parser.add_argument("--state", type=Path, default=Path("reports/topic-state/topic_state.json"))
    parser.add_argument("--out", type=Path, default=Path("reports/topic-state"))
    parser.add_argument("--generated-at", default="", help="ISO timestamp for reproducible historical samples.")
    args = parser.parse_args(argv)
    changes, changes_json, changes_csv = update_topic_state(
        args.candidates,
        args.state,
        args.out,
        generated_at=parse_generated_at(args.generated_at),
    )
    digest = render_change_digest(changes)
    digest_path = args.out / "topic_change_digest.md"
    digest_path.write_text("# Research Question Change Digest\n\n" + digest + "\n", encoding="utf-8")
    print(f"topic_state={args.state}")
    print(f"topic_changes={changes_json}")
    print(f"topic_changes_csv={changes_csv}")
    print(f"topic_change_digest={digest_path}")
    print(f"meaningful_changes={sum(1 for change in changes if change.changed_since_last_push)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
