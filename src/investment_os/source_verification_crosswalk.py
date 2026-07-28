from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .expert_signal_ingest import QUALITY_FORBIDDEN_PHRASES
from .pipeline import DISCLAIMER
from .spike1_research_memo import EvidenceItem, write_ledger

EXPERT_SOURCE_VERIFICATION_CATEGORIES = {
    "expert_source_verification",
    "expert_source_counterevidence",
    "expert_source_gap",
}

REQUIRED_COLUMNS = [
    "expert_symbol",
    "expert_signal_claim",
    "verification_topic",
    "source_type",
    "source_name",
    "source_date",
    "source_url",
    "evidence_direction",
    "evidence_strength",
    "evidence_excerpt",
    "cannot_prove",
    "next_action",
    "status",
]

ALLOWED_DIRECTIONS = {"support", "counter", "gap", "mixed"}
ALLOWED_STRENGTHS = {"verified", "probable", "weak", "blocked"}
ALLOWED_STATUSES = {"ok", "partial", "missing"}


@dataclass
class SourceVerificationResult:
    ledger_csv_path: Path
    ledger_json_path: Path
    crosswalk_path: Path
    quality_scan_path: Path


def _clean(value: str, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).replace("|", "/")
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _category_for(direction: str, strength: str, status: str) -> str:
    if direction == "gap" or strength == "blocked" or status == "missing":
        return "expert_source_gap"
    if direction == "counter":
        return "expert_source_counterevidence"
    return "expert_source_verification"


def _validate_row(row: dict[str, str], source_path: Path) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in row]
    if missing:
        raise ValueError(f"{source_path} missing required columns: {missing}")
    direction = _clean(row["evidence_direction"]).lower()
    strength = _clean(row["evidence_strength"]).lower()
    status = _clean(row["status"]).lower() or "partial"
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError(f"{source_path} has unsupported evidence_direction: {direction}")
    if strength not in ALLOWED_STRENGTHS:
        raise ValueError(f"{source_path} has unsupported evidence_strength: {strength}")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"{source_path} has unsupported status: {status}")
    if status == "ok" and strength not in {"verified", "probable"}:
        raise ValueError(f"{source_path} cannot mark weak/blocked source verification as ok")
    if status == "ok" and not _clean(row.get("source_url", "")):
        raise ValueError(f"{source_path} cannot mark source verification as ok without source_url")


def _row_to_evidence_item(row: dict[str, str], source_path: Path) -> EvidenceItem:
    _validate_row(row, source_path)
    direction = _clean(row["evidence_direction"]).lower()
    strength = _clean(row["evidence_strength"]).lower()
    status = _clean(row["status"]).lower() or "partial"
    category = _category_for(direction, strength, status)
    expert_claim = _clean(row["expert_signal_claim"])
    cannot_prove = _clean(row["cannot_prove"])
    next_action = _clean(row["next_action"])
    source_error = ""
    if status != "ok":
        source_error = json.dumps(
            {
                "code": "source_unavailable" if status == "missing" else "source_partial",
                "message": cannot_prove or "Source verification did not complete.",
                "source_url": _clean(row.get("source_url", "")),
                "transient": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    note = (
        f"Expert signal checked: {expert_claim}; "
        f"Evidence direction={direction}; Evidence strength={strength}; "
        f"Cannot prove: {cannot_prove}; Next action: {next_action}"
        + (f"; Source error={source_error}" if source_error else "")
    )
    return EvidenceItem(
        symbol=_clean(row["expert_symbol"]),
        category=category,
        claim=_clean(row["verification_topic"]),
        value=_clean(row["evidence_excerpt"]),
        source=f"{_clean(row['source_type'])}: {_clean(row['source_name'])}",
        as_of_date=_clean(row["source_date"]),
        freshness=f"source_verification_{strength}",
        status=status,
        url=_clean(row.get("source_url", "")),
        note=note,
    )


def load_source_verification_seed(path: Path) -> list[EvidenceItem]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")
        return [_row_to_evidence_item(row, path) for row in reader if any((value or "").strip() for value in row.values())]


def load_source_verification_seeds(paths: Iterable[Path]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for path in paths:
        items.extend(load_source_verification_seed(path))
    return items


def _parse_note(item: EvidenceItem) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for key in ["Expert signal checked", "Evidence direction", "Evidence strength", "Cannot prove", "Next action"]:
        pattern = rf"{re.escape(key)}=?:\s*(.*?)(?:;\s*(?:Expert signal checked|Evidence direction|Evidence strength|Cannot prove|Next action)[:=]|$)"
        match = re.search(pattern, item.note)
        if match:
            parsed[key] = _clean(match.group(1))
    if not parsed.get("Evidence direction"):
        direction_match = re.search(r"Evidence direction=([^;]+)", item.note)
        if direction_match:
            parsed["Evidence direction"] = _clean(direction_match.group(1))
    if not parsed.get("Evidence strength"):
        strength_match = re.search(r"Evidence strength=([^;]+)", item.note)
        if strength_match:
            parsed["Evidence strength"] = _clean(strength_match.group(1))
    return parsed


def _source_label(item: EvidenceItem) -> str:
    label = item.source
    if item.url:
        return f"{label} ({item.url})"
    return label


def render_source_verification_crosswalk(items: list[EvidenceItem], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    verification_items = [item for item in items if item.category in EXPERT_SOURCE_VERIFICATION_CATEGORIES]
    lines: list[str] = []
    lines.append("# Public Expert Signal Source Verification Crosswalk")
    lines.append("")
    lines.append(f"Generated at: `{generated_at.isoformat()}`")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append("Expert signal → Auditable source → What it verifies → What remains unproven → Next action")
    lines.append("")
    lines.append("A source row can verify only the narrow claim it covers. It does not turn expert signals into conclusions, and it does not settle economics, timing, or company exposure without follow-up evidence.")
    lines.append("")
    if not verification_items:
        lines.append("- No source verification rows were recorded.")
        lines.append("")
    else:
        lines.append("| Theme / symbol | Expert signal | Verification topic | Direction | Strength | Auditable source | Source evidence | Still unproven | Next action | Status |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for item in sorted(verification_items, key=lambda row: (row.symbol, row.category, row.claim, row.source)):
            parsed = _parse_note(item)
            lines.append(
                f"| {_clean(item.symbol, 60)} | {_clean(parsed.get('Expert signal checked', ''), 140)} | {_clean(item.claim, 130)} | "
                f"{_clean(parsed.get('Evidence direction', ''), 30)} | {_clean(parsed.get('Evidence strength', item.freshness.replace('source_verification_', '')), 30)} | "
                f"{_clean(_source_label(item), 150)} | {_clean(item.value, 220)} | {_clean(parsed.get('Cannot prove', ''), 170)} | "
                f"{_clean(parsed.get('Next action', ''), 170)} | {item.status} |"
            )
        lines.append("")
    lines.append("Boundary: verification rows support evidence review only; they do not provide portfolio allocation, return promises, or execution instructions.")
    lines.append("")
    return "\n".join(lines)


def scan_source_verification_quality(text: str) -> dict[str, int]:
    lower_text = text.lower()
    return {phrase: lower_text.count(phrase.lower()) for phrase in QUALITY_FORBIDDEN_PHRASES}


def run(seed_paths: list[Path], out_dir: Path, generated_at: datetime | None = None) -> SourceVerificationResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at or datetime.now(timezone.utc)
    items = load_source_verification_seeds(seed_paths)
    crosswalk = render_source_verification_crosswalk(items, generated_at=generated_at)
    quality_scan = scan_source_verification_quality(crosswalk)
    nonzero = {phrase: count for phrase, count in quality_scan.items() if count}
    if nonzero:
        raise RuntimeError(f"Source verification crosswalk quality scan failed: {nonzero}")

    ledger_csv_path = out_dir / "source_verification_evidence_ledger.csv"
    ledger_json_path = out_dir / "source_verification_evidence_ledger.json"
    crosswalk_path = out_dir / "public_source_verification_crosswalk.md"
    quality_scan_path = out_dir / "source_verification_quality_scan.json"

    write_ledger(items, ledger_csv_path, ledger_json_path)
    crosswalk_path.write_text(crosswalk, encoding="utf-8")
    quality_scan_path.write_text(json.dumps(quality_scan, ensure_ascii=False, indent=2), encoding="utf-8")
    return SourceVerificationResult(
        ledger_csv_path=ledger_csv_path,
        ledger_json_path=ledger_json_path,
        crosswalk_path=crosswalk_path,
        quality_scan_path=quality_scan_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize auditable source checks for public expert signals.")
    parser.add_argument("--seed", dest="seeds", type=Path, nargs="+", required=True, help="CSV seed file(s) with source verification rows.")
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
