from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from .evidence_contract import infer_body_read_status



@dataclass
class SourceCandidate:
    item_id: str
    lane: str
    title: str
    summary: str
    source: str
    source_type: str
    as_of_date: str
    tickers: str = ""
    themes: str = ""
    source_url: str = ""
    source_authority: int = 3
    freshness: int = 3
    evidence_change: int = 3
    magnitude: int = 3
    novelty: int = 3
    decision_usefulness: int = 3
    portfolio_relevance: int = 1
    confidence: str = "probable"
    next_check: str = ""
    kill_signal: str = ""
    cannot_prove: str = ""
    thesis_key: str = ""
    research_question: str = ""
    thesis_impact: str = "unknown"
    counter_explanation: str = ""
    next_primary_source: str = ""
    evidence_status: str = ""
    geography: str = ""
    evidence_digest: str = ""
    observed_value: str = ""
    retrieved_at: str = ""
    body_read_status: str = ""
    content_hash: str = ""
    freshness_status: str = ""
    source_errors: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        from .judgment_kernel import enrich_candidate_row

        if self.evidence_status == "primary_read" and not self.body_read_status:
            self.body_read_status = "legacy_read"
        self.body_read_status = infer_body_read_status(
            self.source_type, self.content_hash, self.body_read_status
        )
        enriched = enrich_candidate_row(asdict(self))
        for attribute in (
            "thesis_key",
            "research_question",
            "thesis_impact",
            "counter_explanation",
            "next_primary_source",
            "evidence_status",
            "geography",
        ):
            if attribute == "evidence_status" or not getattr(self, attribute):
                setattr(self, attribute, str(enriched[attribute]))
        if not self.freshness_status:
            self.freshness_status = "stale" if self.evidence_status == "stale" else "current"

    @property
    def total_score(self) -> int:
        return (
            self.source_authority
            + self.freshness
            + self.evidence_change
            + self.magnitude
            + self.novelty
            + self.decision_usefulness
            + self.portfolio_relevance
        )

    def to_row(self) -> dict[str, str | int]:
        row = asdict(self)
        row["total_score"] = self.total_score
        return row


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _load_source_universe(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _bounded(value: int) -> int:
    return max(1, min(5, int(value)))


def _mk_candidate(
    item_id: str,
    lane: str,
    title: str,
    summary: str,
    source: str,
    source_type: str,
    as_of_date: str,
    **kwargs,
) -> SourceCandidate:
    score_fields = {
        key: _bounded(kwargs.pop(key))
        for key in list(kwargs.keys())
        if key
        in {
            "source_authority",
            "freshness",
            "evidence_change",
            "magnitude",
            "novelty",
            "decision_usefulness",
            "portfolio_relevance",
        }
    }
    return SourceCandidate(
        item_id=item_id,
        lane=lane,
        title=title,
        summary=summary,
        source=source,
        source_type=source_type,
        as_of_date=as_of_date,
        **score_fields,
        **kwargs,
    )


def _latest_macro_candidates(rows: list[dict[str, str]], run_date: str) -> list[SourceCandidate]:
    proxy_rows = [row for row in rows if row.get("category") == "macro_sector_context"]
    by_claim: dict[str, dict[str, str]] = {}
    for row in proxy_rows:
        claim = row.get("claim", "")
        key = claim.split(" context:", 1)[0]
        by_claim[key] = row
    candidates: list[SourceCandidate] = []
    for key, row in by_claim.items():
        value = row.get("value", "")
        lane = "macro_regime" if key in {"SPY", "TLT", "UUP"} else "market_action"
        decision = 4 if key in {"SPY", "XLK", "TLT", "UUP"} else 3
        candidates.append(
            _mk_candidate(
                item_id=f"{lane}:{key}",
                lane=lane,
                title=f"{key} market context changed enough to keep in the daily map",
                summary=value,
                source=row.get("source", "OpenBB/yfinance"),
                source_type="market_data",
                as_of_date=row.get("as_of_date") or run_date,
                tickers=key,
                themes="rates,dollar,technology,market breadth" if lane == "macro_regime" else "sector relative strength",
                source_authority=4,
                freshness=5 if row.get("freshness") == "fresh" else 3,
                evidence_change=3,
                magnitude=4 if "60D=" in value else 3,
                novelty=2,
                decision_usefulness=decision,
                portfolio_relevance=3 if key in {"SPY", "XLK"} else 2,
                confidence="verified",
                next_check="Compare against yields, USD and sector ETF leadership before interpreting single-name moves.",
                kill_signal="If follow-up price and source data stop confirming the move, downgrade to background context.",
            )
        )
    return candidates


def _company_event_candidates(rows: list[dict[str, str]], run_date: str) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    fundamentals = [row for row in rows if row.get("category") in {"fundamentals", "profitability", "valuation", "financial_health"}]
    seen_symbols = sorted({row.get("symbol", "") for row in fundamentals if row.get("symbol")})
    for symbol in seen_symbols:
        sym_rows = [row for row in fundamentals if row.get("symbol") == symbol]
        metrics = "; ".join(f"{row.get('claim')}: {row.get('value')}" for row in sym_rows[:4])
        candidates.append(
            _mk_candidate(
                item_id=f"company_events:{symbol}:financial_snapshot",
                lane="company_events",
                title=f"{symbol} financial snapshot sets the baseline for the coming earnings check",
                summary=metrics,
                source="FinanceToolkit / public financial data",
                source_type="company_financials",
                as_of_date=sym_rows[0].get("as_of_date") or run_date,
                tickers=symbol,
                themes="earnings,margin,valuation,balance sheet",
                source_authority=4,
                freshness=3,
                evidence_change=3,
                magnitude=3,
                novelty=2,
                decision_usefulness=4 if symbol in {"MSFT", "NVDA", "GOOGL", "AMZN"} else 3,
                portfolio_relevance=4 if symbol in {"MSFT", "NVDA", "GOOGL", "AMZN"} else 2,
                confidence="verified",
                next_check="Read the next earnings release, call transcript, capex guidance and FCF bridge.",
                kill_signal="If current financials are stale or restated, refresh before using in a CXO brief.",
            )
        )
    return candidates


def _theme_candidates(rows: list[dict[str, str]], run_date: str) -> list[SourceCandidate]:
    themes = sorted({row.get("symbol", "") for row in rows if row.get("symbol", "").startswith("theme:")})
    labels = {
        "theme:memory_passives": "Memory/passives look like the next AI infrastructure bottleneck to verify",
        "theme:datacenter_power": "Data-center power and cooling are moving from engineering constraint to market variable",
        "theme:photonics_cpo": "CPO/optical networking stays relevant but still needs deployment evidence",
        "theme:physical_ai_supply_chain": "Physical AI upstream needs revenue evidence before it becomes a main theme",
    }
    candidates: list[SourceCandidate] = []
    for theme in themes:
        theme_rows = [row for row in rows if row.get("symbol") == theme]
        ok_rows = [row for row in theme_rows if row.get("status") == "ok"]
        partial_rows = [row for row in theme_rows if row.get("status") != "ok"]
        title = labels.get(theme, theme.replace("theme:", "").replace("_", " "))
        summary_text = ok_rows[0].get("value", "") if ok_rows else (partial_rows[0].get("claim", "") if partial_rows else title)
        candidates.append(
            _mk_candidate(
                item_id=f"sector_theme_discovery:{theme}",
                lane="sector_theme_discovery",
                title=title,
                summary=summary_text[:260],
                source=ok_rows[0].get("source", "expert/source crosswalk") if ok_rows else "expert/source crosswalk",
                source_type="theme_evidence",
                as_of_date=(ok_rows[0].get("as_of_date") if ok_rows else run_date) or run_date,
                tickers=theme,
                themes=theme.replace("theme:", "").replace("_", ","),
                source_authority=4 if ok_rows else 2,
                freshness=4,
                evidence_change=4 if ok_rows else 2,
                magnitude=4 if theme in {"theme:memory_passives", "theme:datacenter_power"} else 3,
                novelty=4,
                decision_usefulness=5 if theme in {"theme:memory_passives", "theme:datacenter_power"} else 3,
                portfolio_relevance=4 if theme in {"theme:memory_passives", "theme:datacenter_power"} else 2,
                confidence="verified" if ok_rows else "watch-only",
                next_check="Map the theme to revenue, orders, capex, pricing and margin evidence at company level.",
                kill_signal="Downgrade if company filings and orders do not confirm the bottleneck narrative.",
            )
        )
    return candidates


def _china_market_candidates(rows: list[dict[str, str]], run_date: str) -> list[SourceCandidate]:
    china_rows = [row for row in rows if row.get("category", "").startswith("china_")]
    if not china_rows:
        return []
    usable = [row for row in china_rows if row.get("status") == "ok"]
    if not usable:
        return []
    symbols = sorted({row.get("symbol", "") for row in usable if row.get("symbol")})
    details: list[str] = []
    for symbol in symbols:
        symbol_rows = [row for row in usable if row.get("symbol") == symbol]
        metrics = "; ".join(
            f"{row.get('claim')}: {row.get('value')}"
            for row in symbol_rows[:3]
        )
        details.append(f"{symbol}: {metrics}")
    as_of_date = max((row.get("as_of_date") or run_date) for row in usable)
    return [
        _mk_candidate(
            item_id="market_action:china_market_breadth",
            lane="market_action",
            title="China market breadth check is available but cross-source reconciliation is incomplete",
            summary=" | ".join(details)[:500],
            source="AKShare / Eastmoney / Sina index feeds",
            source_type="china_market_data_single_source",
            as_of_date=as_of_date,
            tickers=",".join(symbols),
            themes="china,market breadth,liquidity",
            source_authority=3,
            freshness=5,
            evidence_change=3,
            magnitude=3,
            novelty=2,
            decision_usefulness=3,
            portfolio_relevance=3,
            confidence="single_source_pending_reconciliation",
            next_check="Cross-check the same close, daily move and liquidity fields through Tushare before interpreting a China regime change.",
            kill_signal="If AKShare and Tushare disagree materially, keep the China move as an unresolved data issue.",
            cannot_prove="A single-source market snapshot does not prove a broad China regime change or its cause.",
            thesis_key="china:market-breadth",
            research_question="中国市场这次变化是广度与流动性同步变化，还是单一行情源造成的表象？",
            thesis_impact="unknown",
            counter_explanation="Tushare 尚未完成二源核验；单一行情快照不能证明中国市场状态已经改变。",
            next_primary_source="Tushare 同口径行情、交易所数据与当天政策原文。",
            evidence_status="single_source_data",
            geography="China",
        )
    ]


def _hard_source_candidates(path: Path | None) -> list[SourceCandidate]:
    if not path or not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    rows = _read_csv(path)
    candidates: list[SourceCandidate] = []
    for row in rows:
        candidates.append(
            _mk_candidate(
                item_id=row.get("item_id", ""),
                lane=row.get("lane", ""),
                title=row.get("title", ""),
                summary=row.get("summary", ""),
                source=row.get("source", ""),
                source_type=row.get("source_type", ""),
                as_of_date=row.get("as_of_date", ""),
                tickers=row.get("tickers", ""),
                themes=row.get("themes", ""),
                source_url=row.get("source_url", ""),
                source_authority=int(float(row.get("source_authority") or 3)),
                freshness=int(float(row.get("freshness") or 3)),
                evidence_change=int(float(row.get("evidence_change") or 3)),
                magnitude=int(float(row.get("magnitude") or 3)),
                novelty=int(float(row.get("novelty") or 3)),
                decision_usefulness=int(float(row.get("decision_usefulness") or 3)),
                portfolio_relevance=int(float(row.get("portfolio_relevance") or 1)),
                confidence=row.get("confidence", "probable"),
                next_check=row.get("next_check", ""),
                kill_signal=row.get("kill_signal", ""),
                cannot_prove=row.get("cannot_prove", ""),
                evidence_digest=row.get("evidence_digest", ""),
                observed_value=row.get("observed_value", ""),
                retrieved_at=row.get("retrieved_at", ""),
                body_read_status=row.get("body_read_status", ""),
                content_hash=row.get("content_hash", ""),
                freshness_status=row.get("freshness_status", ""),
            )
        )
    return candidates


def collect_source_candidates(
    ledger_csv_path: Path,
    source_universe_path: Path = Path("configs/investment_source_universe.yaml"),
    generated_at: datetime | None = None,
    hard_sources_csv_path: Path | None = None,
) -> list[SourceCandidate]:
    generated_at = generated_at or datetime.now(timezone.utc)
    run_date = generated_at.date().isoformat()
    _load_source_universe(source_universe_path)  # validates that the routing file can be read.
    rows = _read_csv(ledger_csv_path)
    candidates: list[SourceCandidate] = []
    candidates.extend(_latest_macro_candidates(rows, run_date))
    candidates.extend(_company_event_candidates(rows, run_date))
    candidates.extend(_theme_candidates(rows, run_date))
    candidates.extend(_china_market_candidates(rows, run_date))
    candidates.extend(_hard_source_candidates(hard_sources_csv_path))
    return rank_source_candidates(candidates)


def rank_source_candidates(candidates: Iterable[SourceCandidate], max_items: int | None = None) -> list[SourceCandidate]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.decision_usefulness,
            item.evidence_change,
            item.source_authority,
            item.portfolio_relevance,
            item.magnitude,
            item.novelty,
            item.freshness,
            item.title,
        ),
        reverse=True,
    )
    return ranked[:max_items] if max_items else ranked


def rank_with_coverage(
    candidates: list[SourceCandidate],
    max_items: int,
    required_geographies: tuple[str, ...] = ("US", "China"),
) -> list[SourceCandidate]:
    ranked = rank_source_candidates(candidates)
    if max_items <= 0:
        return []
    selected = ranked[:max_items]
    for geography in required_geographies:
        if any(candidate.geography == geography for candidate in selected):
            continue
        replacement = next((candidate for candidate in ranked if candidate.geography == geography), None)
        if replacement is None:
            continue
        counts = {value: sum(candidate.geography == value for candidate in selected) for value in required_geographies}
        replace_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if selected[index].geography not in required_geographies
                or counts.get(selected[index].geography, 0) > 1
            ),
            len(selected) - 1,
        )
        selected[replace_index] = replacement
    rank_position = {candidate.item_id: index for index, candidate in enumerate(ranked)}
    return sorted(selected, key=lambda candidate: rank_position[candidate.item_id])


def write_candidates(candidates: list[SourceCandidate], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "source_universe_candidates.csv"
    json_path = out_dir / "source_universe_candidates.json"
    rows = [candidate.to_row() for candidate in candidates]
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and rank cross-lane investment source-universe candidates.")
    parser.add_argument("--ledger", type=Path, default=Path("reports/us-china-pilot/us_china_evidence_ledger.csv"))
    parser.add_argument("--source-universe", type=Path, default=Path("configs/investment_source_universe.yaml"))
    parser.add_argument("--hard-sources", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("reports/source-universe"))
    parser.add_argument("--max-items", type=int, default=20)
    args = parser.parse_args(argv)
    candidates = collect_source_candidates(args.ledger, args.source_universe, hard_sources_csv_path=args.hard_sources)
    ranked = rank_with_coverage(candidates, max_items=args.max_items)
    csv_path, json_path = write_candidates(ranked, args.out)
    print(f"source_candidates={csv_path}")
    print(f"source_candidates_json={json_path}")
    print(f"candidate_rows={len(ranked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
