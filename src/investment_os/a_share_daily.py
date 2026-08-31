from __future__ import annotations

import csv
import json
import math
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from .spike1_research_memo import EvidenceItem


A_SHARE_TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class AShareSymbol:
    code: str
    name: str = ""


@dataclass(frozen=True)
class AShareDailyResult:
    brief_path: Path
    ledger_path: Path
    coverage_path: Path
    receipt_path: Path
    usable_symbols: int


@dataclass
class SourceReceipt:
    source: str
    status: str
    rows: int
    as_of_date: str
    authority: str
    error: str = ""
    scope: str = "watchlist"


SOURCE_URLS = {
    "AKShare.stock_zh_a_hist": "https://quote.eastmoney.com/center/",
    "AKShare.stock_zh_a_daily": "https://finance.sina.com.cn/stock/",
    "AKShare.stock_zh_a_hist_tx": "https://gu.qq.com/",
    "AKShare.stock_institute_hold_detail": "https://vip.stock.finance.sina.com.cn/q/go.php/vComStockHold/kind/jgcg/index.phtml",
    "AKShare.stock_lhb_jgmmtj_em": "https://data.eastmoney.com/stock/jgmmtj.html",
    "AKShare.stock_dzjy_mrmx": "https://data.eastmoney.com/dzjy/dzjy_mrmx.html",
    "AKShare.stock_margin_detail_sse": "https://www.sse.com.cn/market/othersdata/margin/detail/",
    "AKShare.stock_margin_detail_szse": "https://www.szse.cn/disclosure/margin/margin/index.html",
}


def market_symbol(code: str) -> str:
    normalized = _normalize_code(code)
    if normalized.startswith(("4", "8", "9")):
        return "bj" + normalized
    if normalized.startswith(("5", "6")):
        return "sh" + normalized
    return "sz" + normalized


def _normalize_code(value: Any) -> str:
    text = str(value).strip().lower()
    if text.startswith(("sh", "sz", "bj")):
        text = text[2:]
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(char for char in text if char.isdigit())
    return digits.zfill(6) if digits else text


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _format_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    magnitude = abs(value)
    if magnitude >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿"
    if magnitude >= 10_000:
        return f"{value / 10_000:.2f}万"
    return f"{value:.4g}"


def _as_date_string(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        parsed = pd.to_datetime(value)
        if pd.isna(parsed):
            return "n/a"
        return parsed.date().isoformat()
    except Exception:
        return str(value)[:10]


def _freshness_from_date(as_of: str, stale_after_days: int, reference_at: datetime) -> str:
    try:
        parsed = date.fromisoformat(str(as_of)[:10])
    except Exception:
        return "unknown"
    age = (reference_at.astimezone(A_SHARE_TIMEZONE).date() - parsed).days
    if age < 0:
        return "future_date_check"
    if age <= stale_after_days:
        return "fresh"
    return f"stale_{age}d"


def _column(df: pd.DataFrame, *candidates: str) -> str | None:
    lookup = {str(name).strip().lower(): str(name) for name in df.columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def _retrieved_at(generated_at: datetime) -> str:
    return generated_at.astimezone(timezone.utc).isoformat()


def _evidence(
    symbol: AShareSymbol,
    *,
    category: str,
    claim: str,
    value: str,
    source: str,
    as_of_date: str,
    freshness: str,
    status: str,
    generated_at: datetime,
    authority: str = "convenience_secondary",
    note: str = "",
    cannot_prove: str = "",
) -> EvidenceItem:
    return EvidenceItem(
        symbol=symbol.code,
        category=category,
        claim=claim,
        value=value,
        source=source,
        as_of_date=as_of_date,
        freshness=freshness,
        status=status,
        url=SOURCE_URLS.get(source, ""),
        note=note,
        retrieved_at=_retrieved_at(generated_at),
        body_read_status="structured_data_read" if status in {"ok", "no_event"} else "not_read",
        cannot_prove=cannot_prove,
        source_authority=authority,
        underlying_endpoint=source.removeprefix("AKShare."),
    )


def read_a_share_watchlist(path: Path) -> list[AShareSymbol]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_symbols = payload.get("symbols", [])
    symbols: list[AShareSymbol] = []
    for raw in raw_symbols:
        if isinstance(raw, str):
            code, _, name = raw.partition(":")
        elif isinstance(raw, dict):
            code = str(raw.get("code") or raw.get("symbol") or "")
            name = str(raw.get("name") or "")
        else:
            continue
        code = _normalize_code(code)
        if not code:
            continue
        symbols.append(AShareSymbol(code, name.strip()))
    if not symbols:
        raise ValueError(f"A-share watchlist has no symbols: {path}")
    seen: set[str] = set()
    unique: list[AShareSymbol] = []
    for symbol in symbols:
        if symbol.code not in seen:
            unique.append(symbol)
            seen.add(symbol.code)
    return unique


def _price_provider_calls(ak: Any, symbol: AShareSymbol, start_date: str, end_date: str) -> list[tuple[str, Callable[[], pd.DataFrame]]]:
    calls: list[tuple[str, Callable[[], pd.DataFrame]]] = []
    if hasattr(ak, "stock_zh_a_hist"):
        calls.append((
            "AKShare.stock_zh_a_hist",
            lambda: ak.stock_zh_a_hist(
                symbol=symbol.code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            ),
        ))
    if hasattr(ak, "stock_zh_a_daily"):
        calls.append((
            "AKShare.stock_zh_a_daily",
            lambda: ak.stock_zh_a_daily(
                symbol=market_symbol(symbol.code),
                start_date=start_date,
                end_date=end_date,
                adjust="",
            ),
        ))
    if hasattr(ak, "stock_zh_a_hist_tx") and not symbol.code.startswith(("4", "8", "9")):
        calls.append((
            "AKShare.stock_zh_a_hist_tx",
            lambda: ak.stock_zh_a_hist_tx(
                symbol=market_symbol(symbol.code),
                start_date=start_date,
                end_date=end_date,
                adjust="",
            ),
        ))
    return calls


def fetch_stock_price_evidence(
    symbol: AShareSymbol,
    ak: Any,
    *,
    generated_at: datetime | None = None,
    lookback_days: int = 45,
) -> tuple[list[EvidenceItem], list[str]]:
    generated_at = generated_at or datetime.now(timezone.utc)
    end = generated_at.date().strftime("%Y%m%d")
    start = (generated_at.date() - timedelta(days=lookback_days)).strftime("%Y%m%d")
    errors: list[str] = []
    selected: pd.DataFrame | None = None
    source = ""
    for candidate_source, call in _price_provider_calls(ak, symbol, start, end):
        try:
            frame = call()
            if frame is None or frame.empty:
                errors.append(f"{candidate_source}: empty")
                continue
            selected = frame.copy()
            source = candidate_source
            break
        except Exception as exc:
            errors.append(f"{candidate_source}: {type(exc).__name__}: {exc}")

    if selected is None:
        item = _evidence(
            symbol,
            category="a_share_price",
            claim="A-share daily price history",
            value="unavailable",
            source="AKShare.stock_zh_a_hist",
            as_of_date=generated_at.date().isoformat(),
            freshness="runtime_check",
            status="source_error",
            generated_at=generated_at,
            note=" | ".join(errors)[:1000],
            cannot_prove="No fresh price observation was collected.",
        )
        return [item], errors

    assert selected is not None
    date_col = _column(selected, "date", "日期")
    close_col = _column(selected, "close", "收盘")
    volume_col = _column(selected, "volume", "成交量")
    amount_col = _column(selected, "amount", "成交额")
    if not date_col or not close_col:
        gap = f"{source}: required date/close columns missing"
        item = _evidence(
            symbol,
            category="a_share_price",
            claim="A-share daily price history",
            value="unavailable",
            source=source,
            as_of_date=generated_at.date().isoformat(),
            freshness="runtime_check",
            status="source_error",
            generated_at=generated_at,
            note=gap,
            cannot_prove="The fetched frame could not prove a current close.",
        )
        return [item], [gap]

    selected[date_col] = pd.to_datetime(selected[date_col])
    selected = selected.sort_values(date_col).dropna(subset=[close_col])
    latest = selected.iloc[-1]
    latest_date = _as_date_string(latest[date_col])
    freshness = _freshness_from_date(latest_date, stale_after_days=5, reference_at=generated_at)
    base_status = "ok" if freshness == "fresh" else "stale"
    close = _safe_float(latest[close_col])
    previous_close = _safe_float(selected.iloc[-2][close_col]) if len(selected) >= 2 else None
    change_pct = None if close is None or not previous_close else (close / previous_close - 1.0) * 100
    volume = _safe_float(latest[volume_col]) if volume_col else None
    previous_volumes = pd.to_numeric(selected[volume_col], errors="coerce").iloc[-21:-1] if volume_col else pd.Series(dtype=float)
    comparison_sessions = int(previous_volumes.notna().sum())
    average_volume = _safe_float(previous_volumes.mean()) if not previous_volumes.empty else None
    volume_ratio = None if volume is None or not average_volume else volume / average_volume
    amount = _safe_float(latest[amount_col]) if amount_col else None

    return [
        _evidence(
            symbol,
            category="a_share_price",
            claim="Latest A-share close",
            value=_format_number(close),
            source=source,
            as_of_date=latest_date,
            freshness=freshness,
            status=base_status,
            generated_at=generated_at,
            note=f"provider_fallbacks={len(errors)}",
            cannot_prove="Price action alone cannot prove institutional intent.",
        ),
        _evidence(
            symbol,
            category="a_share_price_change",
            claim="Close-to-close daily price change",
            value=f"{change_pct:.2f}%" if change_pct is not None else "n/a",
            source=source,
            as_of_date=latest_date,
            freshness=freshness,
            status=base_status if change_pct is not None else "missing",
            generated_at=generated_at,
            note=f"numeric={change_pct}" if change_pct is not None else "two observations required",
            cannot_prove="A one-day move cannot establish cause or durable direction.",
        ),
        _evidence(
            symbol,
            category="a_share_volume_ratio",
            claim=f"Latest volume versus prior {comparison_sessions}-session average",
            value=f"{volume_ratio:.2f}x" if volume_ratio is not None else "n/a",
            source=source,
            as_of_date=latest_date,
            freshness=freshness,
            status=base_status if volume_ratio is not None else "missing",
            generated_at=generated_at,
            note=(
                f"numeric={volume_ratio};comparison_sessions={comparison_sessions}"
                if volume_ratio is not None
                else f"insufficient volume history;comparison_sessions={comparison_sessions}"
            ),
            cannot_prove="Volume does not identify the investor type behind a trade.",
        ),
        _evidence(
            symbol,
            category="a_share_turnover_amount",
            claim="Latest daily turnover amount",
            value=_format_number(amount),
            source=source,
            as_of_date=latest_date,
            freshness=freshness,
            status=base_status if amount is not None else "missing",
            generated_at=generated_at,
            note=f"numeric={amount}" if amount is not None else "amount field unavailable",
            cannot_prove="Turnover amount is market activity, not verified institutional flow.",
        ),
    ], []


def _quarter_codes(as_of: date, count: int = 8) -> list[str]:
    quarter = (as_of.month - 1) // 3 + 1
    year = as_of.year
    result: list[str] = []
    for _ in range(count):
        result.append(f"{year}{quarter}")
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4
    return result


def fetch_institutional_holding_evidence(
    symbol: AShareSymbol,
    ak: Any,
    *,
    generated_at: datetime,
) -> tuple[list[EvidenceItem], list[str]]:
    errors: list[str] = []
    successful_empty = False
    for quarter in _quarter_codes(generated_at.date()):
        try:
            frame = ak.stock_institute_hold_detail(stock=symbol.code, quarter=quarter)
        except Exception as exc:
            errors.append(f"quarter={quarter}: {type(exc).__name__}: {exc}")
            continue
        if frame is None or frame.empty:
            successful_empty = True
            continue
        increase_col = _column(frame, "持股比例增幅")
        institution_col = _column(frame, "持股机构简称", "持股机构全称")
        changes = pd.to_numeric(frame[increase_col], errors="coerce") if increase_col else pd.Series(dtype=float)
        increased = int((changes > 0).sum()) if not changes.empty else 0
        decreased = int((changes < 0).sum()) if not changes.empty else 0
        unchanged = int((changes == 0).sum()) if not changes.empty else 0
        top_names = []
        if institution_col:
            top_names = [str(value).strip() for value in frame[institution_col].dropna().head(3) if str(value).strip()]
        value = f"quarter={quarter};records={len(frame)};increase={increased};decrease={decreased};unchanged={unchanged}"
        return [
            _evidence(
                symbol,
                category="a_share_institutional_holding",
                claim="Latest available institutional holding disclosure",
                value=value,
                source="AKShare.stock_institute_hold_detail",
                as_of_date=f"{quarter[:4]}-Q{quarter[-1]}",
                freshness="reporting_period",
                status="ok",
                generated_at=generated_at,
                note="top_institutions=" + ",".join(top_names),
                cannot_prove="Quarterly disclosure is lagged and does not prove current institutional positioning.",
            )
        ], []

    status = "missing" if successful_empty else "source_error"
    note = "No disclosed rows in checked periods." if successful_empty else " | ".join(errors)[:1000]
    return [
        _evidence(
            symbol,
            category="a_share_institutional_holding",
            claim="Latest available institutional holding disclosure",
            value="unavailable",
            source="AKShare.stock_institute_hold_detail",
            as_of_date=generated_at.date().isoformat(),
            freshness="runtime_check",
            status=status,
            generated_at=generated_at,
            note=note,
            cannot_prove="No usable institutional holding disclosure was collected.",
        )
    ], ([] if successful_empty else errors)


def _safe_batch_call(
    source: str,
    authority: str,
    generated_at: datetime,
    call: Callable[[], pd.DataFrame],
) -> tuple[pd.DataFrame | None, SourceReceipt]:
    try:
        frame = call()
        if frame is None:
            frame = pd.DataFrame()
        return frame, SourceReceipt(
            source=source,
            status="ok",
            rows=len(frame),
            as_of_date=generated_at.date().isoformat(),
            authority=authority,
        )
    except Exception as exc:
        return None, SourceReceipt(
            source=source,
            status="source_error",
            rows=0,
            as_of_date=generated_at.date().isoformat(),
            authority=authority,
            error=f"{type(exc).__name__}: {exc}"[:1000],
        )


def _code_matches(frame: pd.DataFrame, code: str, *columns: str) -> pd.DataFrame:
    column = _column(frame, *columns)
    if not column:
        return frame.iloc[0:0]
    normalized = frame[column].map(_normalize_code)
    return frame[normalized == code]


def _event_evidence(
    symbols: list[AShareSymbol],
    frame: pd.DataFrame | None,
    receipt: SourceReceipt,
    *,
    category: str,
    code_columns: tuple[str, ...],
    date_columns: tuple[str, ...],
    amount_columns: tuple[str, ...],
    generated_at: datetime,
    value_label: str,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for symbol in symbols:
        if frame is None:
            items.append(_evidence(
                symbol,
                category=category,
                claim=value_label,
                value="unavailable",
                source=receipt.source,
                as_of_date=receipt.as_of_date,
                freshness="runtime_check",
                status="source_error",
                generated_at=generated_at,
                note=receipt.error,
                cannot_prove="The event source could not be read.",
            ))
            continue
        matched = _code_matches(frame, symbol.code, *code_columns)
        if matched.empty:
            items.append(_evidence(
                symbol,
                category=category,
                claim=value_label,
                value="no_event",
                source=receipt.source,
                as_of_date=receipt.as_of_date,
                freshness="fresh",
                status="no_event",
                generated_at=generated_at,
                note=f"searched_rows={len(frame)}",
                cannot_prove="No matching event in this source window does not prove no institutional activity elsewhere.",
            ))
            continue
        date_col = _column(matched, *date_columns)
        amount_col = _column(matched, *amount_columns)
        event_date = _as_date_string(matched[date_col].max()) if date_col else receipt.as_of_date
        numeric_amounts = (
            pd.to_numeric(matched[amount_col], errors="coerce").dropna()
            if amount_col
            else pd.Series(dtype=float)
        )
        total_amount = float(numeric_amounts.sum()) if not numeric_amounts.empty else None
        items.append(_evidence(
            symbol,
            category=category,
            claim=value_label,
            value=f"events={len(matched)};amount={total_amount if total_amount is not None else 'n/a'}",
            source=receipt.source,
            as_of_date=event_date,
            freshness=_freshness_from_date(event_date, stale_after_days=35, reference_at=generated_at),
            status="ok" if total_amount is not None else "partial",
            generated_at=generated_at,
            note=f"events={len(matched)};amount_field={'usable' if total_amount is not None else 'unavailable'}",
            cannot_prove="An event record does not by itself establish motive or future direction.",
        ))
    return items


def _fetch_margin(
    ak: Any,
    exchange: str,
    generated_at: datetime,
) -> tuple[pd.DataFrame | None, SourceReceipt]:
    function_name = "stock_margin_detail_sse" if exchange == "sse" else "stock_margin_detail_szse"
    source = f"AKShare.{function_name}"
    function = getattr(ak, function_name)
    errors: list[str] = []
    for offset in range(10):
        query_date = (generated_at.date() - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            frame = function(date=query_date)
            if frame is not None and not frame.empty:
                return frame, SourceReceipt(
                    source=source,
                    status="ok",
                    rows=len(frame),
                    as_of_date=(generated_at.date() - timedelta(days=offset)).isoformat(),
                    authority="official_public_data_via_adapter",
                )
        except Exception as exc:
            errors.append(f"{query_date}: {type(exc).__name__}: {exc}")
    return None, SourceReceipt(
        source=source,
        status="source_error",
        rows=0,
        as_of_date=generated_at.date().isoformat(),
        authority="official_public_data_via_adapter",
        error=" | ".join(errors)[:1000] or "no non-empty trading-day response",
    )


def _margin_evidence(
    symbols: list[AShareSymbol],
    frames: dict[str, pd.DataFrame | None],
    receipts: dict[str, SourceReceipt],
    generated_at: datetime,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for symbol in symbols:
        if market_symbol(symbol.code).startswith("bj"):
            items.append(_evidence(
                symbol,
                category="a_share_margin",
                claim="Latest exchange margin-financing detail",
                value="not_applicable",
                source="SSE/SZSE margin-detail feeds",
                as_of_date=generated_at.date().isoformat(),
                freshness="not_applicable",
                status="not_applicable",
                generated_at=generated_at,
                authority="official_public_data",
                note="Beijing Stock Exchange symbols are not routed to Shanghai or Shenzhen margin endpoints.",
                cannot_prove="No margin conclusion is made for this symbol.",
            ))
            continue
        exchange = "sse" if symbol.code.startswith(("5", "6")) else "szse"
        frame = frames[exchange]
        receipt = receipts[exchange]
        if frame is None:
            status = "source_error"
            value = "unavailable"
            note = receipt.error
        else:
            matched = _code_matches(frame, symbol.code, "标的证券代码", "证券代码")
            if matched.empty:
                status = "missing"
                value = "no_row"
                note = "The stock may not be margin-eligible or the source has no row."
            else:
                row = matched.iloc[0]
                balance_col = _column(matched, "融资余额")
                buy_col = _column(matched, "融资买入额")
                balance = _safe_float(row[balance_col]) if balance_col else None
                buy = _safe_float(row[buy_col]) if buy_col else None
                status = "ok"
                value = f"financing_balance={balance if balance is not None else 'n/a'};financing_buy={buy if buy is not None else 'n/a'}"
                note = "Exchange-published margin detail."
        items.append(_evidence(
            symbol,
            category="a_share_margin",
            claim="Latest exchange margin-financing detail",
            value=value,
            source=receipt.source,
            as_of_date=receipt.as_of_date,
            freshness=_freshness_from_date(receipt.as_of_date, stale_after_days=5, reference_at=generated_at),
            status=status,
            generated_at=generated_at,
            authority=receipt.authority,
            note=note,
            cannot_prove="Margin financing includes multiple investor types and is not institutional net flow.",
        ))
    return items


def _offline_evidence(symbols: list[AShareSymbol], generated_at: datetime) -> tuple[list[EvidenceItem], list[SourceReceipt]]:
    items: list[EvidenceItem] = []
    changes = [1.18, -3.25, 2.42]
    ratios = [1.60, 1.15, 2.10]
    for index, symbol in enumerate(symbols):
        change = changes[index % len(changes)]
        ratio = ratios[index % len(ratios)]
        items.extend([
            _evidence(symbol, category="a_share_price", claim="Latest A-share close", value=f"{50 + index * 10:.2f}", source="AKShare.stock_zh_a_daily", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="ok", generated_at=generated_at, cannot_prove="Synthetic offline fixture."),
            _evidence(symbol, category="a_share_price_change", claim="Close-to-close daily price change", value=f"{change:.2f}%", source="AKShare.stock_zh_a_daily", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="ok", generated_at=generated_at, note=f"numeric={change}", cannot_prove="Synthetic offline fixture."),
            _evidence(symbol, category="a_share_volume_ratio", claim="Latest volume versus prior 20-session average", value=f"{ratio:.2f}x", source="AKShare.stock_zh_a_daily", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="ok", generated_at=generated_at, note=f"numeric={ratio}", cannot_prove="Synthetic offline fixture."),
            _evidence(symbol, category="a_share_margin", claim="Latest exchange margin-financing detail", value=f"financing_balance={1_000_000_000 + index * 100_000_000};financing_buy={80_000_000 + index * 10_000_000}", source="AKShare.stock_margin_detail_sse" if symbol.code.startswith("6") else "AKShare.stock_margin_detail_szse", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="ok", generated_at=generated_at, authority="official_public_data_via_adapter", cannot_prove="Synthetic offline fixture."),
            _evidence(symbol, category="a_share_institutional_holding", claim="Latest available institutional holding disclosure", value="quarter=20253;records=2;increase=1;decrease=1;unchanged=0", source="AKShare.stock_institute_hold_detail", as_of_date="2025-Q3", freshness="reporting_period", status="ok", generated_at=generated_at, cannot_prove="Synthetic offline fixture."),
        ])
        if index == 1:
            items.append(_evidence(symbol, category="a_share_lhb", claim="Institutional LHB activity", value="events=1;amount=125000000", source="AKShare.stock_lhb_jgmmtj_em", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="ok", generated_at=generated_at, cannot_prove="Synthetic offline fixture."))
        else:
            items.append(_evidence(symbol, category="a_share_lhb", claim="Institutional LHB activity", value="no_event", source="AKShare.stock_lhb_jgmmtj_em", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="no_event", generated_at=generated_at, cannot_prove="Synthetic offline fixture."))
        items.append(_evidence(symbol, category="a_share_block_trade", claim="A-share block-trade activity", value="no_event", source="AKShare.stock_dzjy_mrmx", as_of_date=generated_at.date().isoformat(), freshness="fresh", status="no_event", generated_at=generated_at, cannot_prove="Synthetic offline fixture."))
    receipts = [
        SourceReceipt("offline_fixture", "ok", len(items), generated_at.date().isoformat(), "synthetic_test_only")
    ]
    return items, receipts


def _parse_value(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in value.split(";"):
        key, separator, raw = part.partition("=")
        if separator:
            result[key] = raw
    return result


def _evidence_by_symbol(items: list[EvidenceItem]) -> dict[str, dict[str, EvidenceItem]]:
    grouped: dict[str, dict[str, EvidenceItem]] = {}
    for item in items:
        grouped.setdefault(item.symbol, {})[item.category] = item
    return grouped


def render_a_share_brief(
    symbols: list[AShareSymbol],
    evidence: list[EvidenceItem],
    *,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    grouped = _evidence_by_symbol(evidence)
    candidates: list[tuple[int, str]] = []
    strong_event_symbols: set[str] = set()

    for symbol in symbols:
        rows = grouped.get(symbol.code, {})
        score = 0
        observations: list[str] = []

        lhb = rows.get("a_share_lhb")
        if lhb and lhb.status in {"ok", "partial"}:
            data = _parse_value(lhb.value)
            amount = _safe_float(data.get("amount"))
            if amount is None:
                observations.append(f"出现{data.get('events', 'n/a')}条龙虎榜机构席位记录，但金额字段不可用")
            elif amount > 0:
                observations.append(f"龙虎榜机构席位净买入{_format_number(amount)}")
            elif amount < 0:
                observations.append(f"龙虎榜机构席位净卖出{_format_number(abs(amount))}")
            else:
                observations.append("龙虎榜机构席位净额为0")
            score += 5
            strong_event_symbols.add(symbol.code)

        block = rows.get("a_share_block_trade")
        if block and block.status in {"ok", "partial"}:
            data = _parse_value(block.value)
            amount = _safe_float(data.get("amount"))
            if amount is None:
                observations.append(f"出现{data.get('events', 'n/a')}笔大宗交易，但成交额字段不可用")
            else:
                observations.append(f"出现{data.get('events', 'n/a')}笔大宗交易，成交额约{_format_number(amount)}")
            score += 3
            strong_event_symbols.add(symbol.code)

        holding = rows.get("a_share_institutional_holding")
        if holding and holding.status == "ok":
            data = _parse_value(holding.value)
            increased = int(float(data.get("increase", "0") or 0))
            decreased = int(float(data.get("decrease", "0") or 0))
            if increased or decreased:
                observations.append(f"最新可得机构披露中，增持条目{increased}个、减持条目{decreased}个")

        price = rows.get("a_share_price_change")
        volume = rows.get("a_share_volume_ratio")
        price_change = _safe_float(price.value.rstrip("%")) if price and price.status == "ok" else None
        volume_ratio = _safe_float(volume.value.rstrip("x")) if volume and volume.status == "ok" else None
        if price_change is not None and abs(price_change) >= 3:
            observations.append(f"股价当日{'上涨' if price_change >= 0 else '下跌'}{abs(price_change):.2f}%")
            score += 1
        if volume is not None and volume_ratio is not None and volume_ratio >= 1.5:
            volume_meta = _parse_value(volume.note)
            session_count = volume_meta.get("comparison_sessions")
            window_label = f"前{session_count}个交易日" if session_count else "近期"
            observations.append(f"成交量约为{window_label}均值的{volume_ratio:.2f}倍")
            score += 1

        margin = rows.get("a_share_margin")
        if margin and margin.status == "ok" and score > 0:
            data = _parse_value(margin.value)
            financing_buy = _safe_float(data.get("financing_buy"))
            if financing_buy is not None:
                observations.append(f"当日融资买入额约{_format_number(financing_buy)}；它不等同于机构净流入")

        if score > 0 and observations:
            name = symbol.name or symbol.code
            sentence = "；".join(observations[:3]) + "。"
            candidates.append((score, f"**{name}（{symbol.code}）**：{sentence}"))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    if strong_event_symbols:
        judgment = f"近30天有{len(strong_event_symbols)}只标的出现可核对的观察事件，但没有显示机构形成一致方向。先看事件本身，不把成交或融资数据冒充机构净流入。"
    else:
        judgment = "今天没有足够强的机构行为信号。价格和成交变化可以记录，但还不能据此判断机构方向。"

    lines = [
        f"# A股机构观察｜{generated_at.date().isoformat()}",
        "",
        f"**今天的判断：**{judgment}",
    ]
    if candidates:
        lines.append("")
        for index, (_, sentence) in enumerate(candidates[:4], start=1):
            lines.append(f"{index}. {sentence}")
    lines.extend([
        "",
        "**下一步只看：**新的龙虎榜机构席位、大宗交易、交易所两融变化，以及下一期机构持股披露是否彼此印证。",
        "",
        "本简报用于研究观察，不是交易建议。",
    ])
    brief = "\n".join(lines)
    if len(brief) > 1200:
        brief = "\n".join(lines[:7] + lines[-3:])
    return brief


def render_coverage_matrix(symbols: list[AShareSymbol], evidence: list[EvidenceItem]) -> str:
    grouped = _evidence_by_symbol(evidence)
    categories = [
        ("价格", "a_share_price"),
        ("机构持股", "a_share_institutional_holding"),
        ("龙虎榜", "a_share_lhb"),
        ("大宗交易", "a_share_block_trade"),
        ("两融", "a_share_margin"),
    ]
    lines = [
        "# A股机构观察覆盖矩阵",
        "",
        "`no_event` 表示来源成功返回但观察窗口内没有该标的事件；`source_error` 表示来源未能读取。两者不可互换。",
        "",
        "| 标的 | " + " | ".join(label for label, _ in categories) + " |",
        "|---|" + "---|" * len(categories),
    ]
    for symbol in symbols:
        rows = grouped.get(symbol.code, {})
        statuses = [rows[key].status if key in rows else "missing" for _, key in categories]
        lines.append(f"| {symbol.name or symbol.code}（{symbol.code}） | " + " | ".join(statuses) + " |")
    return "\n".join(lines) + "\n"


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_ledger(path: Path, evidence: list[EvidenceItem]) -> None:
    rows = [asdict(item) for item in evidence]
    fieldnames = list(EvidenceItem.__dataclass_fields__.keys())
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def count_usable_symbols(symbols: list[AShareSymbol], evidence: list[EvidenceItem]) -> int:
    usable_codes = {
        item.symbol
        for item in evidence
        if item.category == "a_share_price" and item.status == "ok"
    }
    return sum(symbol.code in usable_codes for symbol in symbols)


def run_a_share_daily(
    config_path: Path,
    out_dir: Path,
    *,
    offline: bool = False,
    generated_at: datetime | None = None,
    lookback_days: int = 30,
) -> AShareDailyResult:
    generated_at = generated_at or datetime.now(timezone.utc)
    symbols = read_a_share_watchlist(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    if offline:
        evidence, receipts = _offline_evidence(symbols, generated_at)
    else:
        import akshare as ak

        evidence = []
        receipts: list[SourceReceipt] = []
        for symbol in symbols:
            price_items, price_gaps = fetch_stock_price_evidence(symbol, ak, generated_at=generated_at)
            evidence.extend(price_items)
            receipts.append(SourceReceipt(
                source=price_items[0].source,
                status=price_items[0].status,
                rows=sum(item.status in {"ok", "stale"} for item in price_items),
                as_of_date=price_items[0].as_of_date,
                authority="convenience_secondary",
                error=" | ".join(price_gaps)[:1000],
                scope=symbol.code,
            ))
            holding_items, holding_gaps = fetch_institutional_holding_evidence(symbol, ak, generated_at=generated_at)
            evidence.extend(holding_items)
            receipts.append(SourceReceipt(
                source="AKShare.stock_institute_hold_detail",
                status=holding_items[0].status,
                rows=1 if holding_items[0].status == "ok" else 0,
                as_of_date=holding_items[0].as_of_date,
                authority="convenience_secondary",
                error=" | ".join(holding_gaps)[:1000],
                scope=symbol.code,
            ))

        start = (generated_at.date() - timedelta(days=lookback_days)).strftime("%Y%m%d")
        end = generated_at.date().strftime("%Y%m%d")
        lhb_frame, lhb_receipt = _safe_batch_call(
            "AKShare.stock_lhb_jgmmtj_em",
            "convenience_secondary",
            generated_at,
            lambda: ak.stock_lhb_jgmmtj_em(start_date=start, end_date=end),
        )
        block_frame, block_receipt = _safe_batch_call(
            "AKShare.stock_dzjy_mrmx",
            "convenience_secondary",
            generated_at,
            lambda: ak.stock_dzjy_mrmx(symbol="A股", start_date=start, end_date=end),
        )
        evidence.extend(_event_evidence(
            symbols,
            lhb_frame,
            lhb_receipt,
            category="a_share_lhb",
            code_columns=("代码", "证券代码"),
            date_columns=("上榜日期", "交易日期"),
            amount_columns=("机构买入净额",),
            generated_at=generated_at,
            value_label="Institutional LHB activity",
        ))
        evidence.extend(_event_evidence(
            symbols,
            block_frame,
            block_receipt,
            category="a_share_block_trade",
            code_columns=("证券代码", "代码"),
            date_columns=("交易日期",),
            amount_columns=("成交额",),
            generated_at=generated_at,
            value_label="A-share block-trade activity",
        ))
        receipts.extend([lhb_receipt, block_receipt])

        margin_frames: dict[str, pd.DataFrame | None] = {}
        margin_receipts: dict[str, SourceReceipt] = {}
        for exchange in ("sse", "szse"):
            margin_frames[exchange], margin_receipts[exchange] = _fetch_margin(ak, exchange, generated_at)
        evidence.extend(_margin_evidence(symbols, margin_frames, margin_receipts, generated_at))
        receipts.extend(margin_receipts.values())

    brief_path = out_dir / "brief.md"
    ledger_path = out_dir / "evidence-ledger.csv"
    coverage_path = out_dir / "coverage-matrix.md"
    receipt_path = out_dir / "source-receipt.json"
    _atomic_write_text(brief_path, render_a_share_brief(symbols, evidence, generated_at=generated_at))
    _write_ledger(ledger_path, evidence)
    _atomic_write_text(coverage_path, render_coverage_matrix(symbols, evidence))

    usable_symbols = count_usable_symbols(symbols, evidence)
    receipt_payload = {
        "schema_version": 1,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "mode": "offline" if offline else "live",
        "keyless": True,
        "tushare_required": False,
        "symbols": [asdict(symbol) for symbol in symbols],
        "usable_symbols": usable_symbols,
        "sources": [asdict(receipt) for receipt in receipts],
        "status_counts": {
            status: sum(item.status == status for item in evidence)
            for status in sorted({item.status for item in evidence})
        },
        "outputs": [brief_path.name, ledger_path.name, coverage_path.name, receipt_path.name],
    }
    _atomic_write_text(receipt_path, json.dumps(receipt_payload, ensure_ascii=False, indent=2) + "\n")
    return AShareDailyResult(brief_path, ledger_path, coverage_path, receipt_path, usable_symbols)
