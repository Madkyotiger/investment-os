from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .evidence_contract import infer_body_read_status, normalize_evidence_status
from .http_client import HttpClient, HttpRequestError
from .macro_sources import (
    MacroObservation,
    collect_macro_observations,
    load_macro_series,
    load_market_stale_after_days,
    observation_freshness,
    parse_latest_observation,
)


_HTTP_CLIENT = HttpClient()
_LAST_SOURCE_ERRORS: list[dict[str, object]] = []
RELEVANT_SEC_FORMS = frozenset({"10-K", "10-Q", "8-K", "4"})
BUSINESS_FILING_FORMS = frozenset({"10-K", "10-Q", "8-K"})


@dataclass
class HardSourceCandidate:
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
    source_authority: int = 5
    freshness: int = 4
    evidence_change: int = 3
    magnitude: int = 3
    novelty: int = 3
    decision_usefulness: int = 4
    portfolio_relevance: int = 1
    confidence: str = "verified"
    next_check: str = ""
    kill_signal: str = ""
    cannot_prove: str = ""
    thesis_impact: str = "unknown"
    counter_explanation: str = ""
    next_primary_source: str = ""
    observed_value: str = ""
    revision: float | None = None
    retrieved_at: str = ""
    body_read_status: str = ""
    content_hash: str = ""
    freshness_status: str = "current"
    freshness_threshold_days: int = 3
    evidence_status: str = ""
    source_errors: list[dict[str, object]] = field(default_factory=list)
    accession_number: str = ""

    def __post_init__(self) -> None:
        self.body_read_status = infer_body_read_status(
            self.source_type, self.content_hash, self.body_read_status
        )
        self.evidence_status = normalize_evidence_status(asdict(self))

    def to_row(self) -> dict[str, str | int]:
        return asdict(self)


def _load_watchlist(path: Path) -> dict[str, list[str]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    groups = raw.get("groups", {}) if raw else {}
    return {group: [str(symbol) for symbol in data.get("symbols", [])] for group, data in groups.items()}


def _load_symbol_metadata(path: Path) -> dict[str, dict[str, object]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    metadata = raw.get("symbol_metadata", {}) if raw else {}
    if not isinstance(metadata, dict):
        return {}
    return {
        str(symbol).upper(): dict(values)
        for symbol, values in metadata.items()
        if isinstance(values, dict)
    }


def _flatten_watchlist(groups: dict[str, list[str]]) -> set[str]:
    symbols: set[str] = set()
    for values in groups.values():
        symbols.update(values)
    return symbols


def _watchlist_tags(symbol: str, groups: dict[str, list[str]]) -> list[str]:
    return [group for group, symbols in groups.items() if symbol in symbols]


def _record_source_error(error: HttpRequestError) -> None:
    _LAST_SOURCE_ERRORS.append(error.to_dict())


def get_last_source_errors() -> list[dict[str, object]]:
    return [dict(error) for error in _LAST_SOURCE_ERRORS]


def _http_json(url: str, timeout: int = 10) -> dict | list:
    return _HTTP_CLIENT.get_json(url)


def _http_text(url: str, timeout: int = 10) -> str:
    return _HTTP_CLIENT.get_text(url)


def _safe_float(value: Any) -> float | None:
    try:
        if value in {None, "", "."}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_sec_recent() -> dict:
    try:
        data = _http_json("https://www.sec.gov/files/company_tickers.json")
        if isinstance(data, dict):
            return data
    except HttpRequestError as error:
        _record_source_error(error)
        return {}
    return {}


def collect_sec_watchlist_candidates(watchlist_groups: dict[str, list[str]], generated_at: datetime) -> list[HardSourceCandidate]:
    symbols = _flatten_watchlist(watchlist_groups)
    sec_map = _safe_sec_recent()
    candidates: list[HardSourceCandidate] = []
    for row in sec_map.values():
        ticker = str(row.get("ticker", "")).upper()
        if ticker not in symbols:
            continue
        cik = str(row.get("cik_str", ""))
        title = str(row.get("title", ticker))
        tags = _watchlist_tags(ticker, watchlist_groups)
        candidates.append(
            HardSourceCandidate(
                item_id=f"primary_sec:{ticker}:company_identity",
                lane="company_events",
                title=f"{ticker} has SEC identity available for primary-source filing checks",
                summary=f"SEC company ticker map resolves {ticker} / {title} to CIK {cik}.",
                source="SEC company_tickers.json",
                source_type="primary_sec_identity",
                as_of_date=generated_at.date().isoformat(),
                tickers=ticker,
                themes=",".join(tags),
                source_url="https://www.sec.gov/files/company_tickers.json",
                source_authority=5,
                freshness=4,
                evidence_change=2,
                magnitude=2,
                novelty=2,
                decision_usefulness=3,
                portfolio_relevance=5 if tags else 2,
                confidence="verified",
                retrieved_at=generated_at.isoformat(),
                next_check="Use the CIK to fetch recent 10-K, 10-Q, 8-K, Form 4 and 13F filing metadata.",
                kill_signal="If SEC identity lookup fails or CIK changes, block filing interpretation until refreshed.",
            )
        )
    return candidates


def _recent_sec_filings_for_cik(cik: str) -> list[dict[str, str]]:
    if not cik:
        return []
    padded = str(cik).zfill(10)
    try:
        data = _http_json(f"https://data.sec.gov/submissions/CIK{padded}.json")
    except HttpRequestError as error:
        _record_source_error(error)
        return []
    recent = data.get("filings", {}).get("recent", {}) if isinstance(data, dict) else {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    filings: list[dict[str, str]] = []
    for index, form in enumerate(forms):
        if str(form) not in RELEVANT_SEC_FORMS:
            continue
        filings.append(
            {
                "form": str(form),
                "filing_date": str(dates[index]) if index < len(dates) else "",
                "accession": str(accessions[index]) if index < len(accessions) else "",
                "primary_doc": str(primary_docs[index]) if index < len(primary_docs) else "",
            }
        )
    return filings


def _latest_sec_filing_for_cik(cik: str) -> dict[str, str] | None:
    filings = _recent_sec_filings_for_cik(cik)
    return filings[0] if filings else None


def _latest_sec_business_filing_for_cik(cik: str) -> dict[str, str] | None:
    return next(
        (filing for filing in _recent_sec_filings_for_cik(cik) if filing["form"] in BUSINESS_FILING_FORMS),
        None,
    )


def collect_sec_recent_filing_candidates(
    watchlist_groups: dict[str, list[str]],
    generated_at: datetime,
    max_symbols: int = 8,
    symbol_metadata: dict[str, dict[str, object]] | None = None,
) -> list[HardSourceCandidate]:
    if symbol_metadata:
        symbols = sorted(
            symbol.upper()
            for symbol, metadata in symbol_metadata.items()
            if str(metadata.get("market", "")).upper() == "US" and bool(metadata.get("sec_filings", False))
        )
    else:
        symbols = sorted(
            {
                symbol.upper()
                for symbol in _flatten_watchlist(watchlist_groups)
                if symbol and symbol.replace("-", "").isalpha()
            }
        )
    sec_map = _safe_sec_recent()
    cik_by_ticker = {str(row.get("ticker", "")).upper(): str(row.get("cik_str", "")) for row in sec_map.values()}
    candidates: list[HardSourceCandidate] = []
    for ticker in symbols[:max_symbols]:
        cik = cik_by_ticker.get(ticker.upper(), "")
        latest = _latest_sec_filing_for_cik(cik)
        if not latest or latest["form"] not in RELEVANT_SEC_FORMS:
            continue
        accession_path = latest["accession"].replace("-", "")
        source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{latest['primary_doc']}" if cik and latest["accession"] and latest["primary_doc"] else "https://data.sec.gov/submissions/"
        tags = _watchlist_tags(ticker, watchlist_groups)
        try:
            filing_age_days = (
                generated_at.date() - datetime.fromisoformat(latest["filing_date"][:10]).date()
            ).days
        except ValueError:
            filing_age_days = 4
        filing_freshness_status = "current" if 0 <= filing_age_days <= 3 else "stale"
        candidates.append(
            HardSourceCandidate(
                item_id=f"primary_sec:{ticker}:latest_filing",
                lane="company_events",
                title=f"{ticker} latest SEC filing is {latest['form']} dated {latest['filing_date']}",
                summary=f"SEC recent submissions show {ticker} latest filing: {latest['form']} on {latest['filing_date']}.",
                source="SEC submissions API",
                source_type="primary_sec_recent_filing",
                as_of_date=latest["filing_date"] or generated_at.date().isoformat(),
                tickers=ticker,
                themes=",".join(tags),
                source_url=source_url,
                source_authority=5,
                freshness=5,
                evidence_change=4,
                magnitude=3,
                novelty=3,
                decision_usefulness=4,
                portfolio_relevance=5,
                confidence="verified_metadata",
                retrieved_at=generated_at.isoformat(),
                freshness_status=filing_freshness_status,
                freshness_threshold_days=3,
                next_check="Read the filing body and transcript before turning metadata into a business conclusion.",
                kill_signal="If latest filing is routine or unrelated to capex/revenue/risk, downgrade it from the CXO brief.",
                cannot_prove="Filing metadata proves a document exists; it does not prove the business implication.",
                accession_number=latest["accession"],
            )
        )
        business_latest = latest if latest["form"] in BUSINESS_FILING_FORMS else _latest_sec_business_filing_for_cik(cik)
        if not business_latest:
            continue
        business_accession_path = business_latest["accession"].replace("-", "")
        source_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{business_accession_path}/"
            f"{business_latest['primary_doc']}"
            if cik and business_latest["accession"] and business_latest["primary_doc"]
            else "https://data.sec.gov/submissions/"
        )
        if not source_url.startswith("https://www.sec.gov/Archives/"):
            continue
        try:
            body = _http_text(source_url, timeout=12)
        except HttpRequestError as error:
            _record_source_error(error)
            continue
        if not body.strip():
            continue
        content_hash = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
        try:
            body_age_days = (
                generated_at.date() - datetime.fromisoformat(business_latest["filing_date"][:10]).date()
            ).days
        except ValueError:
            body_age_days = 4
        body_freshness_status = "current" if 0 <= body_age_days <= 3 else "stale"
        candidates.append(
            HardSourceCandidate(
                item_id=f"primary_sec:{ticker}:{business_latest['accession']}:body",
                lane="company_events",
                title=f"{ticker} {business_latest['form']} primary filing body was retrieved",
                summary=(
                    f"SEC filing body retrieved for {ticker} {business_latest['form']} dated "
                    f"{business_latest['filing_date']}; interpretation remains blocked pending relevant-section review."
                ),
                source="SEC primary filing body",
                source_type="primary_filing_body_read",
                as_of_date=business_latest["filing_date"],
                retrieved_at=generated_at.isoformat(),
                tickers=ticker,
                themes=",".join(tags),
                source_url=source_url,
                source_authority=5,
                freshness=5,
                evidence_change=4,
                magnitude=3,
                novelty=3,
                decision_usefulness=4,
                portfolio_relevance=5,
                confidence="verified_body_retrieval",
                thesis_impact="unknown_narrowed",
                counter_explanation="这份文件可能只是例行披露，或与当前研究问题无关。",
                next_primary_source="文件相关章节、最新业绩会记录与业务附注。",
                next_check="Read the relevant business, risk, MD&A, and event sections before stating an implication.",
                kill_signal="If body retrieval or section extraction is incomplete, do not create a business interpretation.",
                cannot_prove="Body retrieval and hashing do not prove a business implication until relevant sections are read.",
                body_read_status="read",
                content_hash=content_hash,
                freshness_status=body_freshness_status,
                freshness_threshold_days=3,
                evidence_status="primary_body_read",
                accession_number=business_latest["accession"],
            )
        )
    return candidates


def _fred_latest(series_id: str) -> tuple[str, float] | None:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        text = _http_text(url, timeout=12)
    except HttpRequestError as error:
        _record_source_error(error)
        return None
    rows = list(csv.DictReader(text.splitlines()))
    for row in reversed(rows):
        value = _safe_float(row.get(series_id))
        if value is not None:
            return str(row.get("observation_date", "")), value
    return None


def _fred_series_text(series_id: str) -> str:
    return _http_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=12)


def _macro_candidate(observation: MacroObservation, generated_at: datetime, threshold_days: int) -> HardSourceCandidate:
    structured = {
        "series_id": observation.series_id,
        "observation_date": observation.observation_date,
        "level": observation.level,
        "change": observation.change,
        "unit": observation.unit,
    }
    observed_value = json.dumps(structured, sort_keys=True, separators=(",", ":"))
    content_hash = "sha256:" + hashlib.sha256(observed_value.encode("utf-8")).hexdigest()
    display_unit = {"percent": "%", "index": "指数点", "thousands": "千人"}.get(
        observation.unit, observation.unit
    )
    change_text = ""
    if observation.change is not None:
        change_text = f"；较前次发布观测变化 {observation.change:+.4g} {display_unit}"
    revision_text = ""
    if observation.revision is not None:
        revision_text = f"；检测到同日期数值修订 {observation.revision:+.4g} {display_unit}"
    return HardSourceCandidate(
        item_id=f"primary_macro:fred:{observation.series_id}",
        lane="macro_regime",
        title=f"FRED {observation.series_id} 官方观测已更新，待结合相邻数据核验",
        summary=(
            f"FRED {observation.series_id} 在 {observation.observation_date} 的官方观测值为 "
            f"{observation.level:.4g} {display_unit}{change_text}{revision_text}。"
        ),
        source="FRED fredgraph.csv",
        source_type="primary_macro_fred_live",
        as_of_date=observation.observation_date,
        themes="macro,official_observation",
        source_url=observation.source_url,
        source_authority=5,
        freshness=1 if observation.freshness_status == "stale" else 5,
        evidence_change=4,
        magnitude=3,
        novelty=3,
        decision_usefulness=4,
        portfolio_relevance=3,
        confidence="verified_data",
        thesis_impact="unknown_narrowed",
        counter_explanation="相邻官方序列、修订或统计口径可能给出不同解释。",
        next_primary_source="相邻官方序列及下一次正式发布。",
        observed_value=observed_value,
        revision=observation.revision,
        retrieved_at=generated_at.isoformat(),
        next_check="先与相邻官方序列和相关市场价格交叉核验，再解释其含义。",
        kill_signal="若观测已过期、再次修订或与相邻官方数据冲突，只保留为背景。",
        cannot_prove="单个官方宏观观测不能证明市场方向、因果关系或公司层面影响。",
        content_hash=content_hash,
        freshness_status=observation.freshness_status,
        freshness_threshold_days=threshold_days,
    )


def collect_fred_macro_candidates(
    generated_at: datetime,
    *,
    state_path: Path | None = None,
) -> list[HardSourceCandidate]:
    definitions = load_macro_series()
    fetched: dict[str, str] = {}
    usable_definitions = {}
    for series_id, definition in definitions.items():
        try:
            text = _fred_series_text(series_id)
            parse_latest_observation(series_id, text, generated_at, definition)
            fetched[series_id] = text
            usable_definitions[series_id] = definition
        except HttpRequestError as error:
            _record_source_error(error)
        except ValueError as error:
            _LAST_SOURCE_ERRORS.append(
                {
                    "source": "FRED",
                    "code": "invalid_observation",
                    "message": str(error),
                    "source_url": f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                    "transient": False,
                }
            )
    if not usable_definitions:
        return []

    def collect_at(path: Path) -> list[HardSourceCandidate]:
        observations = collect_macro_observations(
            usable_definitions,
            fetch_text=lambda series_id: fetched[series_id],
            state_path=path,
            retrieved_at=generated_at,
        )
        return [
            _macro_candidate(observation, generated_at, definitions[observation.series_id].stale_after_days)
            for observation in observations
        ]

    if state_path is not None:
        return collect_at(state_path)
    with tempfile.TemporaryDirectory(prefix="investment-os-macro-") as temporary:
        return collect_at(Path(temporary) / "macro-state.json")


def collect_fred_yield_candidates(generated_at: datetime) -> list[HardSourceCandidate]:
    definitions = load_macro_series()
    series = {
        "DGS2": definitions["DGS2"].label,
        "DGS10": definitions["DGS10"].label,
        "DGS30": definitions["DGS30"].label,
    }
    latest: dict[str, tuple[str, float]] = {}
    for series_id in series:
        value = _fred_latest(series_id)
        if value:
            latest[series_id] = value
    if not latest:
        return []
    parts = [f"{label} {latest[sid][1]:.2f}% ({latest[sid][0]})" for sid, label in series.items() if sid in latest]
    curve_note = ""
    if "DGS2" in latest and "DGS10" in latest:
        curve_note = f"; 10Y-2Y spread {(latest['DGS10'][1] - latest['DGS2'][1]):.2f}pp"
    as_of = max(date for date, _ in latest.values())
    freshness_threshold_days = min(definitions[series_id].stale_after_days for series_id in latest)
    freshness_status = (
        "stale"
        if any(
            observation_freshness(observation_date, generated_at, definitions[series_id]) == "stale"
            for series_id, (observation_date, _value) in latest.items()
        )
        else "current"
    )
    content_hash = "sha256:" + hashlib.sha256(
        json.dumps(latest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    observed_value = json.dumps(latest, sort_keys=True, separators=(",", ":"))
    return [HardSourceCandidate(
        item_id="primary_macro:fred_yield_curve_live",
        lane="macro_regime",
        title="FRED yield curve live snapshot is available for rate-sensitive equity checks",
        summary=f"FRED latest Treasury constants: {', '.join(parts)}{curve_note}.",
        source="FRED fredgraph.csv",
        source_type="primary_macro_fred_yields_live",
        as_of_date=as_of or generated_at.date().isoformat(),
        tickers="TLT,SPY,QQQ,IWM",
        themes="rates,duration,financing_cost",
        source_url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2,DGS10,DGS30",
        source_authority=5, freshness=1 if freshness_status == "stale" else 5, evidence_change=4, magnitude=4, novelty=3, decision_usefulness=5, portfolio_relevance=4,
        confidence="verified_data",
        thesis_impact="unknown_narrowed",
        counter_explanation="期限溢价或技术性因素可能比政策预期更重要。",
        next_primary_source="FRED 相邻期限序列、官方发布与市场代理资产。",
        observed_value=observed_value,
        retrieved_at=generated_at.isoformat(),
        next_check="Compare yield move with TLT/QQQ/IWM and earnings multiple compression before explaining equity moves.",
        kill_signal="If FRED values are stale or market proxies disagree, keep rates as background rather than causal explanation.",
        cannot_prove="Yield levels alone do not prove equity direction or sector causality.",
        content_hash=content_hash,
        freshness_status=freshness_status,
        freshness_threshold_days=freshness_threshold_days,
    )]


def _download_yfinance_snapshot(symbols: list[str]) -> dict[str, dict[str, float | str]]:
    try:
        import yfinance as yf
    except ImportError:
        _LAST_SOURCE_ERRORS.append(
            {
                "source": "yfinance",
                "lane": "market_action",
                "code": "unavailable",
                "message": "yfinance market adapter is unavailable",
                "source_url": "https://query1.finance.yahoo.com/",
                "transient": False,
            }
        )
        return {}
    except Exception:
        _LAST_SOURCE_ERRORS.append(
            {
                "source": "yfinance",
                "lane": "market_action",
                "code": "adapter_error",
                "message": "yfinance market adapter failed to initialize",
                "source_url": "https://query1.finance.yahoo.com/",
                "transient": False,
            }
        )
        return {}
    try:
        data = yf.download(symbols, period="6mo", interval="1d", progress=False, auto_adjust=True, threads=False)
    except Exception:
        _LAST_SOURCE_ERRORS.append(
            {
                "source": "yfinance",
                "lane": "market_action",
                "code": "download_error",
                "message": "yfinance market snapshot download failed",
                "source_url": "https://query1.finance.yahoo.com/",
                "transient": True,
            }
        )
        return {}
    if data is None or getattr(data, "empty", True):
        _LAST_SOURCE_ERRORS.append(
            {
                "source": "yfinance",
                "lane": "market_action",
                "code": "unavailable",
                "message": "yfinance market snapshot returned no usable data",
                "source_url": "https://query1.finance.yahoo.com/",
                "transient": True,
            }
        )
        return {}
    try:
        close = data["Close"]
    except Exception:
        close = data
    snapshots: dict[str, dict[str, float | str]] = {}
    for symbol in symbols:
        try:
            series = close[symbol].dropna() if hasattr(close, "columns") else close.dropna()
        except Exception:
            continue
        if len(series) < 5:
            continue
        last = float(series.iloc[-1])
        prev = float(series.iloc[-2]) if len(series) >= 2 else last
        base_60 = float(series.iloc[-60]) if len(series) >= 60 else float(series.iloc[0])
        snapshots[symbol] = {
            "date": str(series.index[-1].date()) if hasattr(series.index[-1], "date") else str(series.index[-1]),
            "close": round(last, 4),
            "one_day_pct": round((last / prev - 1) * 100, 2) if prev else 0.0,
            "sixty_day_pct": round((last / base_60 - 1) * 100, 2) if base_60 else 0.0,
        }
    return snapshots



def _stooq_symbol(symbol: str) -> str:
    mapping = {"SPY": "spy.us", "QQQ": "qqq.us", "IWM": "iwm.us", "XLK": "xlk.us", "SMH": "smh.us", "TLT": "tlt.us", "UUP": "uup.us"}
    return mapping.get(symbol.upper(), f"{symbol.lower()}.us")


def _download_stooq_snapshot(symbols: list[str]) -> dict[str, dict[str, float | str]]:
    snapshots: dict[str, dict[str, float | str]] = {}
    for symbol in symbols:
        url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(symbol)}&i=d"
        try:
            text = _http_text(url, timeout=10)
            rows = list(csv.DictReader(text.splitlines()))
        except HttpRequestError as error:
            _record_source_error(error)
            continue
        clean = [row for row in rows if _safe_float(row.get("Close")) is not None]
        if len(clean) < 5:
            continue
        last_row = clean[-1]
        prev_row = clean[-2]
        base_row = clean[-60] if len(clean) >= 60 else clean[0]
        last = float(last_row["Close"])
        prev = float(prev_row["Close"])
        base_60 = float(base_row["Close"])
        snapshots[symbol] = {
            "date": str(last_row.get("Date", "")),
            "close": round(last, 4),
            "one_day_pct": round((last / prev - 1) * 100, 2) if prev else 0.0,
            "sixty_day_pct": round((last / base_60 - 1) * 100, 2) if base_60 else 0.0,
        }
    return snapshots


def _cross_check_market_snapshot(primary: dict[str, dict[str, float | str]], secondary: dict[str, dict[str, float | str]]) -> tuple[str, str]:
    if not secondary:
        return "market_data_probable", "二源行情暂未取得；价格变化只作为待核验市场线索。"
    checked = 0
    mismatches: list[str] = []
    for symbol, pdata in primary.items():
        sdata = secondary.get(symbol)
        if not sdata:
            continue
        checked += 1
        pclose = _safe_float(pdata.get("close"))
        sclose = _safe_float(sdata.get("close"))
        if pclose and sclose and abs(pclose / sclose - 1) > 0.03:
            mismatches.append(symbol)
    if checked == 0:
        return "market_data_probable", "二源行情没有覆盖当前代理资产；价格变化只作为待核验市场线索。"
    if mismatches:
        return "market_data_mixed", f"二源行情覆盖 {checked} 个代理资产，但 {', '.join(mismatches)} 收盘价偏差超过 3%。"
    return "market_data_cross_checked", f"Stooq 二源行情已覆盖 {checked} 个代理资产，收盘价未见超过 3% 的偏差。"

def collect_market_move_candidates(watchlist_groups: dict[str, list[str]], generated_at: datetime) -> list[HardSourceCandidate]:
    symbols = watchlist_groups.get("market_proxies", [])[:]
    if not symbols:
        return []
    snapshots = _download_yfinance_snapshot(symbols)
    if not snapshots:
        return []
    secondary = _download_stooq_snapshot(symbols)
    confidence, cross_check_note = _cross_check_market_snapshot(snapshots, secondary)
    source_errors = []
    if confidence == "market_data_mixed":
        source_errors.append(
            {
                "code": "source_conflict",
                "message": cross_check_note,
                "source_url": "https://stooq.com/",
                "transient": False,
            }
        )
    ranked = sorted(snapshots.items(), key=lambda item: abs(float(item[1].get("one_day_pct", 0))), reverse=True)
    top_symbol, top = ranked[0]
    market_freshness_threshold = load_market_stale_after_days()
    try:
        market_age_days = (
            generated_at.date() - datetime.fromisoformat(str(top.get("date", ""))[:10]).date()
        ).days
    except ValueError:
        market_age_days = market_freshness_threshold + 1
    freshness_status = "current" if 0 <= market_age_days <= market_freshness_threshold else "stale"
    top_one_day_move = abs(float(top.get("one_day_pct", 0)))
    summary = "; ".join(f"{symbol}: close {data['close']}, 1D {data['one_day_pct']}%, 60D {data['sixty_day_pct']}%" for symbol, data in ranked[:5])
    summary = f"{summary}. {cross_check_note}"
    observed_value = json.dumps(snapshots, sort_keys=True, separators=(",", ":"))
    evidence_payload = json.dumps(
        {"primary": snapshots, "secondary": secondary},
        sort_keys=True,
        separators=(",", ":"),
    )
    content_hash = "sha256:" + hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest()
    return [HardSourceCandidate(
        item_id="market_live:proxy_moves",
        lane="market_action",
        title=f"Market proxy move is led by {top_symbol} at {top['one_day_pct']}% one-day change",
        summary=summary,
        source="yfinance daily adjusted prices + Stooq cross-check",
        source_type="market_proxy_prices_live",
        as_of_date=str(top.get("date", generated_at.date().isoformat())),
        tickers=",".join(symbols),
        themes="market_proxies",
        source_url="https://query1.finance.yahoo.com/; https://stooq.com/",
        source_authority=4 if confidence == "market_data_cross_checked" else 3,
        freshness=1 if freshness_status == "stale" else 5,
        evidence_change=4 if top_one_day_move >= 1 else 2,
        magnitude=4 if top_one_day_move >= 1 else 2,
        novelty=3, decision_usefulness=4, portfolio_relevance=4,
        confidence=confidence,
        thesis_impact="unknown_narrowed" if top_one_day_move >= 1 else "unknown",
        counter_explanation="价格变化可能只是 beta、流动性或报价差异，不能单独证明原因。",
        next_primary_source="交叉核验行情、官方利率数据与相关公司披露。",
        observed_value=observed_value,
        retrieved_at=generated_at.isoformat(),
        content_hash=content_hash,
        freshness_status=freshness_status,
        freshness_threshold_days=market_freshness_threshold,
        source_errors=source_errors,
        next_check="Use market proxy moves only after cross-checking the quote source and matching them against rates, dollar and sector leadership.",
        kill_signal="If quote sources are stale, unavailable, or materially inconsistent, downgrade market-action commentary.",
        cannot_prove="Price movement does not prove the cause of the move.",
    )]


def collect_macro_hard_candidates(generated_at: datetime) -> list[HardSourceCandidate]:
    # Minimal no-key primary-source skeleton. Values are not pulled yet; this creates source targets
    # that the next hard-source pass can fill with FRED/Treasury observations.
    date = generated_at.date().isoformat()
    return [
        HardSourceCandidate(
            item_id="primary_macro:federal_reserve_calendar",
            lane="macro_regime",
            title="Fed calendar is the primary macro trigger map for rate-path risk",
            summary="The Fed meeting calendar is the official source for upcoming policy dates; use it before interpreting rate-sensitive equity moves.",
            source="Federal Reserve FOMC calendar",
            source_type="primary_macro_calendar",
            as_of_date=date,
            tickers="TLT,UUP,SPY,QQQ",
            themes="rates,dollar,liquidity",
            source_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            source_authority=5,
            freshness=4,
            evidence_change=2,
            magnitude=4,
            novelty=2,
            decision_usefulness=4,
            portfolio_relevance=3,
            confidence="verified_source_target",
            next_check="Fetch the next FOMC date, statement, minutes and dot-plot changes before writing rate-path conclusions.",
            kill_signal="If rate expectations are not confirmed by official Fed material or market pricing, keep macro commentary as background only.",
            cannot_prove="This source target alone does not prove current policy bias or market-implied rate moves.",
        ),
        HardSourceCandidate(
            item_id="primary_macro:treasury_yield_curve",
            lane="macro_regime",
            title="Treasury yield curve should anchor duration-sensitive equity interpretation",
            summary="Treasury yield data is the primary reference for rate pressure on high-duration growth and AI-infrastructure financing assumptions.",
            source="U.S. Treasury daily rates",
            source_type="primary_macro_rates",
            as_of_date=date,
            tickers="TLT,SPY,QQQ,IWM",
            themes="rates,duration,financing_cost",
            source_url="https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
            source_authority=5,
            freshness=4,
            evidence_change=3,
            magnitude=4,
            novelty=2,
            decision_usefulness=4,
            portfolio_relevance=3,
            confidence="verified_source_target",
            next_check="Pull latest 2Y/10Y/30Y yields and compare with TLT and growth-sector relative strength.",
            kill_signal="If yields are stale or unavailable, do not explain equity moves with rates.",
            cannot_prove="This source target does not by itself explain sector price action.",
        ),
    ]


def collect_watchlist_relevance_candidates(watchlist_groups: dict[str, list[str]], generated_at: datetime) -> list[HardSourceCandidate]:
    candidates: list[HardSourceCandidate] = []
    for group, symbols in watchlist_groups.items():
        if not symbols:
            continue
        candidates.append(
            HardSourceCandidate(
                item_id=f"watchlist:{group}",
                lane="portfolio_watchlist",
                title=f"{group} watchlist is active for CXO relevance routing",
                summary=f"Tracking {len(symbols)} symbols: {', '.join(symbols[:12])}.",
                source="configs/watchlist.yaml",
                source_type="watchlist_config",
                as_of_date=generated_at.date().isoformat(),
                tickers=",".join(symbols),
                themes=group,
                source_authority=3,
                freshness=5,
                evidence_change=2,
                magnitude=2,
                novelty=2,
                decision_usefulness=4 if group in {"core_us", "ai_infra"} else 3,
                portfolio_relevance=5,
                confidence="configured",
                next_check="Use this group as a relevance boost, not as holdings or trade intent.",
                kill_signal="If the watchlist becomes stale or starts implying holdings, refresh or split it before pushing CXO briefs.",
                cannot_prove="A watchlist match only proves relevance, not investment merit.",
            )
        )
    return candidates


def collect_hard_source_candidates(
    watchlist_path: Path,
    generated_at: datetime | None = None,
    *,
    macro_state_path: Path | None = None,
) -> list[HardSourceCandidate]:
    generated_at = generated_at or datetime.now(timezone.utc)
    _LAST_SOURCE_ERRORS.clear()
    groups = _load_watchlist(watchlist_path)
    symbol_metadata = _load_symbol_metadata(watchlist_path)
    candidates: list[HardSourceCandidate] = []
    candidates.extend(collect_sec_watchlist_candidates(groups, generated_at))
    candidates.extend(
        collect_sec_recent_filing_candidates(
            groups,
            generated_at,
            symbol_metadata=symbol_metadata,
        )
    )
    candidates.extend(collect_macro_hard_candidates(generated_at))
    if macro_state_path is None:
        candidates.extend(collect_fred_yield_candidates(generated_at))
    else:
        candidates.extend(collect_fred_macro_candidates(generated_at, state_path=macro_state_path))
    candidates.extend(collect_market_move_candidates(groups, generated_at))
    candidates.extend(collect_watchlist_relevance_candidates(groups, generated_at))
    retrieved_at = generated_at.isoformat()
    for candidate in candidates:
        if not candidate.retrieved_at:
            candidate.retrieved_at = retrieved_at
    return candidates


def write_hard_source_candidates(candidates: list[HardSourceCandidate], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "hard_source_candidates.csv"
    json_path = out_dir / "hard_source_candidates.json"
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
    parser = argparse.ArgumentParser(description="Collect primary-source and watchlist relevance candidates for the investment intelligence stack.")
    parser.add_argument("--watchlist", type=Path, default=Path("configs/watchlist.yaml"))
    parser.add_argument("--out", type=Path, default=Path("reports/hard-sources"))
    args = parser.parse_args(argv)
    candidates = collect_hard_source_candidates(args.watchlist)
    csv_path, json_path = write_hard_source_candidates(candidates, args.out)
    print(f"hard_source_candidates={csv_path}")
    print(f"hard_source_candidates_json={json_path}")
    print(f"hard_source_candidate_rows={len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
