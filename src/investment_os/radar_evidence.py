"""First-hand captures the program can fetch for a radar run.

The researching agent keeps doing discovery and reading. This module covers the
official, machine-readable sources that real runs kept citing second-hand or
recording as gaps: rates and macro series, Treasury auction results, exchange
settlement prices, a scheduled official bulletin, and company filings.

Every capture is saved as readable UTF-8 under ``RUN/hard-evidence/`` with its
SHA-256 and described by a SourceManifest row the agent can copy into
``live-packet.json``. Where the source is HTML or JSON the saved body is a plain
text rendering and the raw bytes are kept beside it. A capture states what the
source returned; it carries no interpretation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml

from .http_client import HttpClient, HttpRequestError

EVIDENCE_DIR = "hard-evidence"
MANIFEST_NAME = "hard-sources.json"
DIGEST_NAME = "digest.md"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "pre", "hr", "title"}
_SKIP_TAGS = {"script", "style", "noscript", "ix:header"}
_CELL_TAGS = {"td", "th"}
ATTACHMENT_FORMS = frozenset({"8-K", "6-K"})
RAW_KEEP_BYTES = 262_144  # larger raw responses are hashed, not stored; the URL stays in the manifest
DEFAULT_SEC_FORMS = ("8-K", "10-Q", "10-K", "6-K", "20-F", "S-1", "S-1/A")


@dataclass
class Capture:
    source_id: str
    url: str
    title: str
    text: str
    digest: list[str]
    identity_ok: bool = True
    raw: bytes | None = None
    raw_suffix: str = ""
    publication_time: str = ""
    publication_time_precision: str = ""
    observation_period: str = ""


@dataclass
class CollectionResult:
    sources: list[dict[str, Any]] = field(default_factory=list)
    not_captured: list[dict[str, str]] = field(default_factory=list)
    digest: list[str] = field(default_factory=list)


class _TextExtractor(HTMLParser):
    """Visible text, one table row per line so a figure stays next to its label."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._row = 0

    def _break(self, tag: str) -> None:
        if tag == "tr":
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append(" " if self._row else "\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _CELL_TAGS:
            self.parts.append(" | ")
        else:
            self._break(tag)
            self._row += tag == "tr"

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        else:
            if tag == "tr":
                self._row = max(0, self._row - 1)
            self._break(tag)

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    lines = []
    for line in "".join(parser.parts).splitlines():
        line = re.sub(r"[ \t\xa0]+", " ", line)
        line = re.sub(r"( ?\| ?){2,}", " | ", line).strip(" |")
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"


def _html_title(markup: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", markup, re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip() if match else ""


def _decode(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def _fetch(client: HttpClient, url: str, content_types: tuple[str, ...]) -> bytes:
    return client.get_bytes(url, expected_content_types=content_types)


def capture_fred_series(client: HttpClient, series_id: str, label: str, today: date, history_days: int) -> Capture:
    start = (today - timedelta(days=history_days)).isoformat()
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    text = _decode(_fetch(client, url, ("text/csv", "application/csv", "text/plain")))
    rows = list(csv.reader(text.splitlines()))
    identity_ok = bool(rows) and rows[0] == ["observation_date", series_id]
    observations = [(row[0], row[1]) for row in rows[1:] if len(row) == 2 and row[1] not in ("", ".")]
    digest = [f"{series_id} ({label}): no observation in the last {history_days} days"]
    period = ""
    if observations:
        period, latest = observations[-1]
        digest = [f"{series_id} ({label}): {latest} for {period}"]
        if len(observations) > 1:
            digest[0] += f"; previous {observations[-2][1]} for {observations[-2][0]}"
        digest[0] += ". FRED gives the observation date, not the release date."
    return Capture(
        source_id=f"fred-{series_id.lower()}",
        url=url,
        title=f"FRED {series_id}: {label}",
        text=text if text.endswith("\n") else text + "\n",
        digest=digest,
        identity_ok=identity_ok,
        observation_period=period,
    )


def capture_page(client: HttpClient, source_id: str, url: str, title_contains: str, excerpt_after: str) -> Capture:
    raw = _fetch(client, url, ("text/html",))
    markup = _decode(raw)
    title = _html_title(markup)
    text = html_to_text(markup)
    excerpt = ""
    if excerpt_after and excerpt_after in text:
        excerpt = " ".join(text.split(excerpt_after, 1)[1].split())[:320]
    return Capture(
        source_id=source_id,
        url=url,
        title=title or source_id,
        text=text,
        digest=[f"{title or source_id}: {excerpt or 'captured; read the saved text'}"],
        identity_ok=bool(title_contains) and title_contains.lower() in title.lower(),
        raw=raw,
        raw_suffix=".raw.html",
    )


def capture_treasury_auctions(client: HttpClient, days: int) -> Capture:
    url = f"https://www.treasurydirect.gov/TA_WS/securities/auctioned?format=json&days={days}"
    raw = _fetch(client, url, ("application/json", "text/json"))
    rows = json.loads(_decode(raw))
    identity_ok = isinstance(rows, list) and all(isinstance(row, dict) and "cusip" in row for row in rows)
    lines = [
        "US Treasury auction results (TreasuryDirect)",
        "term | type | auction date | high yield (notes, bonds) or high discount rate (bills) | bid-to-cover | offering amount USD | CUSIP",
    ]
    latest = ""

    def auction_day(row: dict[str, Any]) -> str:
        return str(row.get("competitiveAuctionCloseDate") or row.get("auctionDate") or "")[:10]

    for row in sorted(rows if identity_ok else [], key=auction_day, reverse=True):
        latest = max(latest, auction_day(row))
        rate = str(row.get("highYield") or row.get("highRate") or row.get("highDiscountRate") or "")
        lines.append(" | ".join((
            str(row.get("securityTerm", "")), str(row.get("securityType", "")), auction_day(row) or "n/a",
            f"{rate}%" if rate else "n/a", str(row.get("bidToCoverRatio") or "n/a"),
            str(row.get("offeringAmount") or "n/a"), str(row.get("cusip", "")),
        )))
    return Capture(
        source_id="treasury-auctions",
        url=url,
        title=f"US Treasury auctions, last {days} days",
        text="\n".join(lines) + "\n",
        digest=[f"Treasury auctions in the last {days} days: {max(len(lines) - 2, 0)}"] + [f"  {line}" for line in lines[2:]],
        identity_ok=identity_ok,
        raw=raw,
        raw_suffix=".raw.json",
        observation_period=latest,
    )


def capture_shfe_daily(client: HttpClient, products: dict[str, str], today: date, max_back_days: int = 6) -> Capture:
    last_error: HttpRequestError | None = None
    for offset in range(max_back_days + 1):
        day = today - timedelta(days=offset)
        url = f"https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{day:%Y%m%d}.dat"
        try:
            raw = _fetch(client, url, ("application/json", "text/json", "text/plain", "application/octet-stream"))
            payload = json.loads(_decode(raw))
        except HttpRequestError as error:
            last_error = error
            continue
        except ValueError:
            continue
        rows = payload.get("o_curinstrument") if isinstance(payload, dict) else None
        # The exchange publishes the day's file before settlement with empty prices;
        # only a file that carries settlement prices is a finished trading day.
        if not isinstance(rows, list) or not any(isinstance(row.get("SETTLEMENTPRICE"), (int, float)) for row in rows):
            continue
        lines = [
            f"Shanghai Futures Exchange daily settlement, trading day {day.isoformat()}",
            "product | most-traded contract | settlement | previous settlement | change | volume | open interest",
        ]
        for code, name in products.items():
            contracts = [
                row for row in rows
                if str(row.get("PRODUCTGROUPID", "")).strip() == code
                and str(row.get("DELIVERYMONTH", "")).strip().isdigit()
                and isinstance(row.get("VOLUME"), (int, float))
                and isinstance(row.get("SETTLEMENTPRICE"), (int, float))
            ]
            if not contracts:
                lines.append(f"{name} ({code}) | not in this file")
                continue
            main = max(contracts, key=lambda row: row["VOLUME"])
            lines.append(" | ".join((
                f"{name} ({code})", str(main.get("DELIVERYMONTH", "")).strip(), str(main.get("SETTLEMENTPRICE", "")),
                str(main.get("PRESETTLEMENTPRICE", "")), str(main.get("ZD2_CHG", "")), str(main.get("VOLUME", "")),
                str(main.get("OPENINTEREST", "")),
            )))
        return Capture(
            source_id="shfe-daily",
            url=url,
            title=f"SHFE daily settlement {day.isoformat()}",
            text="\n".join(lines) + "\n",
            digest=[f"SHFE settlement for {day.isoformat()} (prices in CNY per quoted unit):"] + [f"  {line}" for line in lines[2:]],
            raw=raw,
            raw_suffix=".raw.json",
            publication_time=f"{day.isoformat()}T15:00:00+08:00",
            publication_time_precision="date",
            observation_period=day.isoformat(),
        )
    if last_error:
        raise last_error
    raise HttpRequestError("no_data", f"no SHFE daily file in the last {max_back_days} days", "https://www.shfe.com.cn/")


def capture_sec_filings(
    client: HttpClient, tickers: list[str], forms: list[str], today: date, lookback_days: int, max_attachments: int = 3,
) -> tuple[list[Capture], list[dict[str, str]]]:
    captures: list[Capture] = []
    missing: list[dict[str, str]] = []
    try:
        directory = json.loads(_decode(_fetch(client, SEC_TICKERS_URL, ("application/json",))))
    except HttpRequestError as error:
        return [], [{"source_id": f"sec-{ticker.lower()}", "url": SEC_TICKERS_URL, "error": str(error)} for ticker in tickers]
    by_ticker = {str(row.get("ticker", "")).upper(): row for row in directory.values() if isinstance(row, dict)}
    since = (today - timedelta(days=lookback_days)).isoformat()
    for ticker in tickers:
        # A company with no listed ticker yet (for example before its offering) is addressed by its SEC number.
        entry = {"cik_str": int(ticker), "title": f"CIK {int(ticker)}"} if ticker.isdigit() else by_ticker.get(ticker.upper())
        if not entry:
            missing.append({"source_id": f"sec-{ticker.lower()}", "url": SEC_TICKERS_URL, "error": "ticker not in the SEC company list"})
            continue
        cik = int(entry["cik_str"])
        company = str(entry.get("title", ticker))
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        try:
            recent = json.loads(_decode(_fetch(client, submissions_url, ("application/json",))))["filings"]["recent"]
        except (HttpRequestError, KeyError, ValueError) as error:
            missing.append({"source_id": f"sec-{ticker.lower()}", "url": submissions_url, "error": str(error)})
            continue
        found = 0
        for index, form in enumerate(recent.get("form", [])):
            filed = str(recent["filingDate"][index])
            if form not in forms or filed < since:
                continue
            found += 1
            accession = str(recent["accessionNumber"][index])
            folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
            primary = str(recent["primaryDocument"][index])
            accepted = str((recent.get("acceptanceDateTime") or [""] * (index + 1))[index])
            items = str((recent.get("items") or [""] * (index + 1))[index])
            documents = [(primary, "")]
            if form in ATTACHMENT_FORMS:
                # The substance of these forms (earnings release, agreement) sits in the attached documents.
                try:
                    listing = json.loads(_decode(_fetch(client, f"{folder}/index.json", ("application/json",))))
                    attached = [
                        (int(item.get("size") or 0), str(item.get("name", "")))
                        for item in listing["directory"]["item"]
                        if str(item.get("name", "")).lower().endswith((".htm", ".html"))
                        and str(item.get("name", "")) != primary
                        and not re.match(r"(R\d+\.htm|.*-index(-headers)?\.html?)$", str(item.get("name", "")))
                    ]
                    documents += [(name, f"-doc{position}") for position, (_, name) in enumerate(sorted(attached, reverse=True)[:max_attachments], start=1)]
                except (HttpRequestError, KeyError, ValueError):
                    pass  # the primary document is still captured below
            base_id = f"sec-{ticker.lower()}-{re.sub(r'[^a-z0-9]', '', form.lower())}-{filed.replace('-', '')}"
            for name, suffix in documents:
                url = f"{folder}/{name}"
                try:
                    raw = _fetch(client, url, ("text/html", "text/plain", "application/xhtml+xml"))
                except HttpRequestError as error:
                    missing.append({"source_id": base_id + suffix, "url": url, "error": str(error)})
                    continue
                markup = _decode(raw)
                kind = "attached document" if suffix else "primary document"
                detail = f"; 8-K items {items}" if items and not suffix else ""
                captures.append(Capture(
                    source_id=base_id + suffix,
                    url=url,
                    title=_html_title(markup) or f"{company} {form} {kind}",
                    text=html_to_text(markup),
                    digest=[f"{ticker.upper()} {company}: {form} filed {filed}, {kind} ({name}){detail}"],
                    raw=raw,
                    raw_suffix=".raw.html",
                    publication_time=accepted.replace(".000Z", "+00:00") if accepted else "",
                    publication_time_precision="minute" if accepted else "",
                    observation_period=str((recent.get("reportDate") or [""] * (index + 1))[index]),
                ))
        if not found:
            captures.append(Capture(
                source_id=f"sec-{ticker.lower()}-none", url=submissions_url, title="", text="",
                digest=[f"{ticker.upper()} {company}: no {'/'.join(forms)} filed since {since}"],
            ))
    return captures, missing


def _write_capture(capture: Capture, run_dir: Path, now: datetime) -> dict[str, Any]:
    folder = run_dir / EVIDENCE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    body = capture.text.encode("utf-8")
    body_path = folder / f"{capture.source_id}.txt"
    body_path.write_bytes(body)
    stamp = now.isoformat(timespec="seconds")
    row: dict[str, Any] = {
        "source_id": capture.source_id,
        "url": capture.url,
        "requested_url": capture.url,
        "captured_title": capture.title,
        "kind": "evidence",
        "access_completeness": "full",
        "identity_status": "match" if capture.identity_ok else "mismatch",
        "body_path": f"{EVIDENCE_DIR}/{body_path.name}",
        "sha256": hashlib.sha256(body).hexdigest(),
        "captured_at": stamp,
        "accessed_at": stamp,
        "capture_method": "program_http_get",
    }
    if capture.raw is not None:
        row["capture_method"] = "program_http_get+text_rendering"
        row["raw_sha256"] = hashlib.sha256(capture.raw).hexdigest()
        row["raw_bytes"] = len(capture.raw)
        if len(capture.raw) <= RAW_KEEP_BYTES:
            raw_path = folder / f"{capture.source_id}{capture.raw_suffix}"
            raw_path.write_bytes(capture.raw)
            row["raw_body_path"] = f"{EVIDENCE_DIR}/{raw_path.name}"
    if capture.publication_time:
        row["publication_time"] = capture.publication_time
        row["publication_time_precision"] = capture.publication_time_precision
    if capture.observation_period:
        row["observation_period"] = capture.observation_period
    return row


def collect(
    run_dir: Path,
    config: dict[str, Any],
    now: datetime,
    sec_tickers: list[str] | None = None,
    client: HttpClient | None = None,
) -> CollectionResult:
    client = client or HttpClient(timeout_seconds=25, max_response_bytes=25_000_000)
    today = now.date()
    result = CollectionResult()
    jobs: list[tuple[str, str, Any]] = []
    fred = config.get("fred") or {}
    for series_id, label in (fred.get("series") or {}).items():
        jobs.append((f"fred-{series_id.lower()}", "https://fred.stlouisfed.org/", lambda s=series_id, t=label: capture_fred_series(
            client, s, str(t), today, int(fred.get("history_days", 120)))))
    for page in config.get("pages") or []:
        jobs.append((str(page["id"]), str(page["url"]), lambda p=page: capture_page(
            client, str(p["id"]), str(p["url"]), str(p.get("title_contains", "")), str(p.get("excerpt_after", "")))))
    if "treasury_auctions" in config:
        days = int((config["treasury_auctions"] or {}).get("days", 7))
        jobs.append(("treasury-auctions", "https://www.treasurydirect.gov/", lambda: capture_treasury_auctions(client, days)))
    if "shfe_daily" in config:
        products = dict((config["shfe_daily"] or {}).get("products") or {})
        jobs.append(("shfe-daily", "https://www.shfe.com.cn/", lambda: capture_shfe_daily(client, products, today)))

    captures: list[Capture] = []
    for source_id, url, job in jobs:
        try:
            captures.append(job())
        except HttpRequestError as error:
            result.not_captured.append({"source_id": source_id, "url": error.source_url or url, "error": str(error)})
        except (ValueError, KeyError, TypeError) as error:
            result.not_captured.append({"source_id": source_id, "url": url, "error": f"unreadable response: {type(error).__name__}"})
    sec = config.get("sec") or {}
    tickers = list(dict.fromkeys([*(sec.get("tickers") or []), *(sec_tickers or [])]))
    if tickers:
        sec_captures, sec_missing = capture_sec_filings(
            client, [str(ticker) for ticker in tickers], [str(form) for form in sec.get("forms") or DEFAULT_SEC_FORMS],
            today, int(sec.get("lookback_days", 4)),
        )
        captures.extend(sec_captures)
        result.not_captured.extend(sec_missing)

    # A later call in the same run (for example --sec after a company reports) adds to
    # what is already there; rows the researcher has copied keep pointing at valid files.
    folder = run_dir / EVIDENCE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / MANIFEST_NAME
    try:
        earlier = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        earlier = {}
    rows: dict[str, dict[str, Any]] = {row["source_id"]: row for row in earlier.get("sources") or []}
    digests: dict[str, list[str]] = dict(earlier.get("digest") or {})
    missing: dict[str, dict[str, str]] = {row["source_id"]: row for row in earlier.get("not_captured") or []}
    for capture in captures:
        lines = list(capture.digest)
        if capture.text.strip():
            row = _write_capture(capture, run_dir, now)
            result.sources.append(row)
            rows[capture.source_id] = row
            if not capture.identity_ok:
                lines.append(f"  WARNING {capture.source_id}: the response is not the requested document (identity_status=mismatch)")
        digests[capture.source_id] = lines
        missing.pop(capture.source_id, None)
        result.digest.extend(lines)
    for row in result.not_captured:
        missing[row["source_id"]] = row
        digests.pop(row["source_id"], None)

    manifest_path.write_text(json.dumps({
        "schema_version": "radar-hard-sources-v1",
        "captured_at": now.isoformat(timespec="seconds"),
        "sources": list(rows.values()),
        "not_captured": list(missing.values()),
        "digest": digests,
        "hash_verifies_bytes_not_truth": True,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# First-hand captures, updated {now.isoformat(timespec='seconds')}",
        "",
        f"Copy the rows you cite from `{MANIFEST_NAME}` into the packet `sources`. A `bounded_quote` must appear literally in the saved `.txt`.",
        "",
        *[line if line.startswith("  ") else f"- {line}" for source_lines in digests.values() for line in source_lines],
    ]
    if missing:
        lines += ["", "## Not captured (record as gaps, not as nothing happened)", ""]
        lines += [f"- {row['source_id']}: {row['error']} ({row['url']})" for row in missing.values()]
    (folder / DIGEST_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch first-hand official captures into a radar run directory.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="Hard-source list, see configs/radar_hard_sources.sample.yaml. Omit to capture only --sec filings.")
    parser.add_argument("--sec", default="", help="Comma-separated tickers (or SEC CIK numbers) whose recent filings to capture.")
    parser.add_argument("--now", help="Timezone-aware capture time (default: current time).")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any requested source was not captured or mismatched.")
    args = parser.parse_args(argv)
    config = (yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}) if args.config else {}
    if not isinstance(config, dict):
        parser.error("config must be a mapping")
    if not args.config and not args.sec.strip():
        parser.error("nothing to capture: give --config, --sec, or both")
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc).astimezone()
    if now.tzinfo is None:
        parser.error("--now must include a timezone offset")
    result = collect(args.run_dir, config, now, [ticker.strip() for ticker in args.sec.split(",") if ticker.strip()])
    mismatched = [row["source_id"] for row in result.sources if row["identity_status"] != "match"]
    print(json.dumps({
        "captured": len(result.sources),
        "not_captured": [row["source_id"] for row in result.not_captured],
        "mismatched": mismatched,
        "digest": str(args.run_dir / EVIDENCE_DIR / DIGEST_NAME),
        "manifest": str(args.run_dir / EVIDENCE_DIR / MANIFEST_NAME),
    }, ensure_ascii=False))
    return 1 if args.strict and (result.not_captured or mismatched) else 0


if __name__ == "__main__":
    raise SystemExit(main())
