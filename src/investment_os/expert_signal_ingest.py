from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .pipeline import DISCLAIMER
from .spike1_research_memo import EvidenceItem, write_ledger

EXPERT_SIGNAL_CATEGORIES = {
    "expert_signal_context",
    "expert_counter_signal",
    "expert_signal_gap",
    "expert_signal_review_question",
}

REQUIRED_COLUMNS = [
    "symbol",
    "category",
    "claim",
    "value",
    "source",
    "as_of_date",
    "freshness",
    "status",
    "url",
    "note",
]

QUALITY_FORBIDDEN_PHRASES = [
    "建议买入",
    "建议卖出",
    "建议持有",
    "建议加仓",
    "建议减仓",
    "买入",
    "卖出",
    "持有",
    "加仓",
    "减仓",
    "清仓",
    "recommend buy",
    "recommend sell",
    "recommend hold",
    "recommendation to buy",
    "recommendation to sell",
    "recommendation to hold",
    "position sizing",
    "目标收益",
    "自动下单",
    "10倍",
    "20倍",
    "10x",
    "20x",
    "韭菜",
    "收割",
    "跟着机构",
    "爆发机会",
    "确定性机会",
    "guaranteed upside",
    "sure thing",
    "follow smart money",
    "/mnt/",
    ".cache",
    "uv run",
    "scripts/",
    "reports/us-china-pilot",
    "info_cache=",
    "markdown_cache=",
    "sections_cache=",
]


@dataclass
class ExpertSignalIngestResult:
    ledger_csv_path: Path
    ledger_json_path: Path
    crosswalk_path: Path
    quality_scan_path: Path


def _clean_public_text(value: str, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).replace("|", "/")
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _normalize_review_question(claim: str, value: str) -> str:
    cleaned = _clean_public_text(value)
    if cleaned.endswith("?"):
        return re.sub(r"\?+$", "?", cleaned)
    claim_text = _clean_public_text(claim, 160).rstrip(" ?")
    return f"Which primary evidence would verify or contradict this expert signal before it becomes a research observation: {claim_text}?"


def _normalize_note(category: str, note: str) -> str:
    cleaned = _clean_public_text(note)
    additions: list[str] = []
    if "evidence strength" not in cleaned.lower():
        additions.append("Evidence strength=weak until linked sources or primary evidence are inspected.")
    if category == "expert_signal_review_question" and "question only" not in cleaned.lower():
        additions.append("Question only; does not support any trade decision or final investment conclusion.")
    if additions:
        cleaned = "; ".join(part for part in [cleaned, *additions] if part)
    return cleaned


def _row_to_evidence_item(row: dict[str, str], source_path: Path) -> EvidenceItem:
    missing = [column for column in REQUIRED_COLUMNS if column not in row]
    if missing:
        raise ValueError(f"{source_path} missing required columns: {missing}")
    category = _clean_public_text(row["category"])
    if category not in EXPERT_SIGNAL_CATEGORIES:
        raise ValueError(f"{source_path} has unsupported expert signal category: {category}")
    claim = _clean_public_text(row["claim"])
    value = _clean_public_text(row["value"])
    if category == "expert_signal_review_question":
        value = _normalize_review_question(claim, value)
    status = _clean_public_text(row["status"]) or "partial"
    if status == "ok":
        status = "partial"
    return EvidenceItem(
        symbol=_clean_public_text(row["symbol"]),
        category=category,
        claim=claim,
        value=value,
        source=_clean_public_text(row["source"]),
        as_of_date=_clean_public_text(row["as_of_date"]),
        freshness=_clean_public_text(row["freshness"]) or "public_expert_signal",
        status=status,
        url=_clean_public_text(row.get("url", "")),
        note=_normalize_note(category, row.get("note", "")),
    )


def load_expert_signal_seed(path: Path) -> list[EvidenceItem]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")
        return [_row_to_evidence_item(row, path) for row in reader if any((value or "").strip() for value in row.values())]


def load_expert_signal_seeds(paths: Iterable[Path]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for path in paths:
        items.extend(load_expert_signal_seed(path))
    return items


def _signal_type(item: EvidenceItem) -> str:
    return {
        "expert_signal_context": "context signal",
        "expert_counter_signal": "counter-signal",
        "expert_signal_gap": "source gap",
        "expert_signal_review_question": "review question",
    }[item.category]


def research_question_for_signal(item: EvidenceItem) -> str:
    if item.category == "expert_signal_review_question":
        return _normalize_review_question(item.claim, item.value)
    claim = _clean_public_text(item.claim, 160)
    return f"Which primary evidence would verify or contradict this expert signal before it becomes a research observation: {claim}?"


def _next_source_for_signal(item: EvidenceItem) -> str:
    note = item.note
    lowered = note.lower()
    for marker in ["verify with ", "inspect ", "require "]:
        idx = lowered.find(marker)
        if idx == -1:
            continue
        fragment = note[idx + len(marker):]
        fragment = re.split(r"[.;]", fragment, maxsplit=1)[0]
        return _clean_public_text(fragment, 160)
    claim = item.claim.lower()
    if "bottleneck" in claim or "infrastructure" in claim:
        return "supplier filings, capex disclosure, lead times, pricing, and margin evidence"
    if "capex" in claim or "fcf" in claim:
        return "capex, free-cash-flow, debt, and management-commentary evidence"
    if "valuation" in claim:
        return "valuation assumptions, margin, growth, and peer-methodology checks"
    return "primary source, linked research, filing, financial metric, or counterevidence"


def _support_gap_text(item: EvidenceItem) -> str:
    if item.category == "expert_signal_gap":
        return "Source gap: not yet verified by primary evidence; treat as blocked or partial until an auditable source is inspected."
    if item.category == "expert_counter_signal":
        return "Counter-signal: not yet verified by primary evidence; use to test the attractive thesis, not to replace it."
    if item.category == "expert_signal_review_question":
        return "Derived question: not yet verified by primary evidence; use as a review prompt only."
    return "Context signal: not yet verified by primary evidence; use as question fuel only."


def render_public_expert_signal_crosswalk(items: list[EvidenceItem], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    expert_items = [item for item in items if item.category in EXPERT_SIGNAL_CATEGORIES]
    lines: list[str] = []
    lines.append("# Public Expert Signal Crosswalk")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("Signal → Evidence support/conflict/gap → Research question → Next source")
    lines.append("")
    lines.append("Public expert signals are angle-discovery inputs. They are not yet verified by primary evidence unless the linked source has been inspected.")
    lines.append("")
    if not expert_items:
        lines.append("- No public expert signal rows were recorded.")
        lines.append("")
    else:
        lines.append("| Theme / symbol | Type | Public signal | Evidence support / conflict / gap | Research question | Next source | Status | URL |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for item in sorted(expert_items, key=lambda row: (row.symbol, row.category, row.claim)):
            lines.append(
                f"| {_clean_public_text(item.symbol, 60)} | {_signal_type(item)} | {_clean_public_text(item.claim, 140)} | "
                f"{_support_gap_text(item)} | {_clean_public_text(research_question_for_signal(item), 220)} | "
                f"{_clean_public_text(_next_source_for_signal(item), 160)} | {item.status} | {_clean_public_text(item.url, 90)} |"
            )
        lines.append("")
    lines.append("Boundary: this crosswalk supports evidence checks and research questions only; it does not provide trade instructions, allocation guidance, price targets, or return promises.")
    lines.append("")
    return "\n".join(lines)


def scan_expert_signal_crosswalk_quality(text: str) -> dict[str, int]:
    lower_text = text.lower()
    return {phrase: lower_text.count(phrase.lower()) for phrase in QUALITY_FORBIDDEN_PHRASES}


def run(seed_paths: list[Path], out_dir: Path, generated_at: datetime | None = None) -> ExpertSignalIngestResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at or datetime.now(timezone.utc)
    items = load_expert_signal_seeds(seed_paths)
    crosswalk = render_public_expert_signal_crosswalk(items, generated_at=generated_at)
    quality_scan = scan_expert_signal_crosswalk_quality(crosswalk)
    nonzero = {phrase: count for phrase, count in quality_scan.items() if count}
    if nonzero:
        raise RuntimeError(f"Expert signal crosswalk quality scan failed: {nonzero}")

    ledger_csv_path = out_dir / "expert_signal_evidence_ledger.csv"
    ledger_json_path = out_dir / "expert_signal_evidence_ledger.json"
    crosswalk_path = out_dir / "public_expert_signal_crosswalk.md"
    quality_scan_path = out_dir / "expert_signal_quality_scan.json"

    write_ledger(items, ledger_csv_path, ledger_json_path)
    crosswalk_path.write_text(crosswalk, encoding="utf-8")
    quality_scan_path.write_text(json.dumps(quality_scan, ensure_ascii=False, indent=2), encoding="utf-8")
    return ExpertSignalIngestResult(
        ledger_csv_path=ledger_csv_path,
        ledger_json_path=ledger_json_path,
        crosswalk_path=crosswalk_path,
        quality_scan_path=quality_scan_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize public expert signals into Evidence Ledger rows and a safe crosswalk.")
    parser.add_argument("--seed", dest="seeds", type=Path, nargs="+", required=True, help="CSV seed file(s) with expert signal rows.")
    parser.add_argument("--out", type=Path, default=Path("reports/expert-signals"))
    args = parser.parse_args(argv)
    result = run(args.seeds, out_dir=args.out)
    print(f"ledger_csv={result.ledger_csv_path}")
    print(f"ledger_json={result.ledger_json_path}")
    print(f"crosswalk={result.crosswalk_path}")
    print(f"quality_scan={result.quality_scan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
