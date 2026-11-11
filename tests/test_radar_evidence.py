import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from investment_os.cli import main
from investment_os.http_client import HttpClient
from investment_os.radar_evidence import collect, html_to_text
from investment_os.upstream_radar import evaluate_packet, load_objective

NOW = datetime.fromisoformat("2026-11-11T07:20:00+08:00")
SEC_FOLDER = "https://www.sec.gov/Archives/edgar/data/1477333/000147733326000060"
RESPONSES: dict[str, tuple[str, str]] = {
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=2026-07-14": (
        "text/csv", "observation_date,DGS10\n2026-11-06,4.86\n2026-11-09,4.88\n2026-11-10,.\n"),
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=WRONG&cosd=2026-07-14": (
        "text/csv", "observation_date,OTHER\n2026-11-09,1\n"),
    "https://example.gov/enso": (
        "text/html", "<html><head><title>ENSO Diagnostic Discussion</title><script>x()</script></head>"
        "<body><p>Synopsis: El Ni&ntilde;o continues.</p><table><tr><td><p>Revenue</p></td><td>$</td><td>3,661</td></tr></table></body></html>"),
    "https://www.treasurydirect.gov/TA_WS/securities/auctioned?format=json&days=7": ("application/json", json.dumps([
        {"cusip": "91282CRX1", "securityTerm": "10-Year", "securityType": "Note", "competitiveAuctionCloseDate": "2026-11-10T00:00:00",
         "highYield": "5.020", "bidToCoverRatio": "2.46", "offeringAmount": "42000000000"},
        {"cusip": "912797TC1", "securityTerm": "6-Week", "securityType": "Bill", "competitiveAuctionCloseDate": "2026-11-09T00:00:00",
         "highRate": "3.990", "bidToCoverRatio": "2.59", "offeringAmount": "100000000000"},
    ])),
    # Today's exchange file exists before settlement, with empty prices.
    "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20261111.dat": ("application/json", json.dumps({"o_curinstrument": [
        {"PRODUCTGROUPID": "cu", "DELIVERYMONTH": "2612", "SETTLEMENTPRICE": "", "VOLUME": 92600}]})),
    "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20261110.dat": ("application/json", json.dumps({"o_curinstrument": [
        {"PRODUCTGROUPID": "cu", "DELIVERYMONTH": "2611", "SETTLEMENTPRICE": 107630, "PRESETTLEMENTPRICE": 107550, "ZD2_CHG": 80, "VOLUME": 15865, "OPENINTEREST": 24865},
        {"PRODUCTGROUPID": "cu", "DELIVERYMONTH": "2612", "SETTLEMENTPRICE": 105880, "PRESETTLEMENTPRICE": 105350, "ZD2_CHG": 530, "VOLUME": 83603, "OPENINTEREST": 192075},
        {"PRODUCTGROUPID": "cu", "DELIVERYMONTH": "小计", "SETTLEMENTPRICE": "", "VOLUME": 99468},
    ]})),
    "https://www.sec.gov/files/company_tickers.json": ("application/json", json.dumps({"0": {"cik_str": 1477333, "ticker": "NET", "title": "Cloudflare, Inc."}})),
    "https://data.sec.gov/submissions/CIK0001477333.json": ("application/json", json.dumps({"filings": {"recent": {
        "form": ["8-K", "4", "8-K"], "filingDate": ["2026-11-10", "2026-11-09", "2026-10-01"],
        "accessionNumber": ["0001477333-26-000060", "0001477333-26-000059", "0001477333-26-000050"],
        "primaryDocument": ["cloud-20261110.htm", "form4.xml", "old.htm"],
        "acceptanceDateTime": ["2026-11-10T21:18:21.000Z", "", ""], "items": ["2.02,9.01", "", "5.02"], "reportDate": ["2026-11-10", "", ""],
    }}})),
    f"{SEC_FOLDER}/index.json": ("application/json", json.dumps({"directory": {"item": [
        {"name": "0001477333-26-000060-index.html", "size": ""}, {"name": "cloud-20261110.htm", "size": "29142"},
        {"name": "q326earningspress.htm", "size": "447771"}, {"name": "R1.htm", "size": "38099"}, {"name": "logo.jpg", "size": "45607"},
    ]}})),
    f"{SEC_FOLDER}/cloud-20261110.htm": ("text/html", "<html><title>8-K</title><body><ix:header><p>hidden facts</p></ix:header><p>Item 2.02 Results of Operations</p></body></html>"),
    # The title of this release changes every quarter; the body marker identifies it.
    "https://www.bls.gov/news.release/prod2.nr0.htm": (
        "text/html", "<html><head><title> Third Quarter 2026, Preliminary\r\n - 2026 Q03 Results </title></head><body><pre>"
        "PRODUCTIVITY AND COSTS\nThird Quarter 2026, Preliminary\n\nNonfarm business sector labor productivity increased 3.6 percent</pre></body></html>"),
    "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/wasde": ("application/json", json.dumps({"results": [
        {"id": "1", "title": "World Agricultural Supply and Demand Estimates", "identifier": ["wasde"], "release_datetime": "2026-10-09T12:00:00+0000",
         "files": ["https://esmis.nal.usda.gov/sites/default/release-files/1/wasde1026.txt"]},
        {"id": "2", "title": "World Agricultural Supply and Demand Estimates", "identifier": ["wasde"], "release_datetime": "2026-11-10T12:00:00+0000",
         "files": ["https://esmis.nal.usda.gov/sites/default/release-files/2/wasde1126.pdf", "https://esmis.nal.usda.gov/sites/default/release-files/2/wasde1126.txt"]},
    ]})),
    "https://esmis.nal.usda.gov/sites/default/release-files/2/wasde1126.txt": (
        "text/plain", "   WASDE - 677 - 8      November 2026\r\n\r\nWheat\r\n   Nov     827.51    1110.36\r\n"),
    "https://esmis.nal.usda.gov/api/v1/release/findByIdentifier/pdfonly": ("application/json", json.dumps({"results": [
        {"id": "3", "title": "Some Report", "identifier": ["pdfonly"], "release_datetime": "2026-11-10T12:00:00+0000", "files": ["https://esmis.nal.usda.gov/x.pdf"]},
    ]})),
    f"{SEC_FOLDER}/q326earningspress.htm": ("text/html", "<html><body><p>Cloudflare Announces Third Quarter Results</p><table><tr><td>Revenue</td><td>$</td><td><div>562.0</div></td></tr></table></body></html>"),
}


class _Response:
    def __init__(self, content_type: str, body: str) -> None:
        self.headers = {"Content-Type": content_type}
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _limit: int) -> bytes:
        return self._body


def _client() -> HttpClient:
    def opener(request, timeout):
        url = request.full_url
        if url not in RESPONSES:
            import urllib.error

            raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)
        return _Response(*RESPONSES[url])

    return HttpClient(opener=opener, max_attempts=1)


CONFIG = {
    "fred": {"history_days": 120, "series": {"DGS10": "US 10-year yield, percent"}},
    "treasury_auctions": {"days": 7},
    "shfe_daily": {"products": {"cu": "Copper", "ni": "Nickel"}},
    "pages": [{"id": "enso", "url": "https://example.gov/enso", "title_contains": "ENSO Diagnostic Discussion", "excerpt_after": "Synopsis:"}],
    "sec": {"forms": ["8-K", "10-Q"], "lookback_days": 4},
}


@pytest.fixture(autouse=True)
def _sec_identity(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_IDENTITY", "Example Research research@example.com")


def test_table_rows_stay_on_one_line_and_hidden_blocks_are_dropped():
    text = html_to_text("<ix:header><p>hidden</p></ix:header><p>Head</p><table><tr><td><p>Revenue</p></td><td></td><td>$</td><td>3,661</td></tr></table>")

    assert text == "Head\nRevenue | $ | 3,661\n"


def test_collect_writes_hashed_captures_the_validator_accepts(tmp_path: Path):
    result = collect(tmp_path, CONFIG, NOW, sec_tickers=["NET"], client=_client())

    ids = [row["source_id"] for row in result.sources]
    assert ids == ["fred-dgs10", "enso", "treasury-auctions", "shfe-daily", "sec-net-8k-20261110", "sec-net-8k-20261110-doc1"]
    assert result.not_captured == []
    for row in result.sources:
        body = (tmp_path / row["body_path"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == row["sha256"]
        assert row["identity_status"] == "match" and row["kind"] == "evidence"
    digest = (tmp_path / "hard-evidence" / "digest.md").read_text(encoding="utf-8")
    assert "DGS10 (US 10-year yield, percent): 4.88 for 2026-11-09; previous 4.86 for 2026-11-06" in digest
    assert "10-Year | Note | 2026-11-10 | 5.020% | 2.46" in digest
    assert "6-Week | Bill | 2026-11-09 | 3.990%" in digest
    # The unfinished 11-11 file is skipped; the most-traded contract of the finished day is reported.
    shfe = (tmp_path / "hard-evidence" / "shfe-daily.txt").read_text(encoding="utf-8")
    assert "trading day 2026-11-10" in shfe and "Copper (cu) | 2612 | 105880 | 105350 | 530" in shfe
    assert "Nickel (ni) | not in this file" in shfe
    assert "Revenue | $ | 562.0" in (tmp_path / "hard-evidence" / "sec-net-8k-20261110-doc1.txt").read_text(encoding="utf-8")
    assert "hidden facts" not in (tmp_path / "hard-evidence" / "sec-net-8k-20261110.txt").read_text(encoding="utf-8")
    sec_row = result.sources[4]
    assert sec_row["publication_time"] == "2026-11-10T21:18:21+00:00" and sec_row["publication_time_precision"] == "minute"
    assert (tmp_path / sec_row["raw_body_path"]).is_file() and sec_row["raw_bytes"] > 0


    objective = load_objective(Path("configs/upstream_radar.sample.yaml"))
    packet = {
        "schema_version": "upstream-radar-packet-v2",
        "as_of": "2026-11-11T07:30:00+08:00",
        "run_id": "2026-11-11-073000",
        "sources": result.sources,
        "coverage": [
            {"domain": domain, "check": check, "status": "checked", "source_ids": ids}
            for domain, checks in objective.required_checks.items() for check in checks
        ],
        "items": [],
    }
    result = evaluate_packet(packet, objective, run_dir=tmp_path)
    assert result.gaps == () and result.errors == ()
    assert all(row["verified_source_ids"] == ids for row in result.coverage)


def test_failed_and_mismatched_sources_are_reported_not_hidden(tmp_path: Path, capsys):
    config = {"fred": {"series": {"WRONG": "mislabelled"}}, "pages": [{"id": "blocked", "url": "https://example.gov/blocked", "title_contains": "x"}]}
    result = collect(tmp_path, config, NOW, sec_tickers=["ZZZZ"], client=_client())

    assert [row["identity_status"] for row in result.sources] == ["mismatch"]
    assert [row["source_id"] for row in result.not_captured] == ["blocked", "sec-zzzz"]
    assert "http_status status=403" in result.not_captured[0]["error"]
    digest = (tmp_path / "hard-evidence" / "digest.md").read_text(encoding="utf-8")
    assert "## Not captured (record as gaps, not as nothing happened)" in digest
    assert "WARNING fred-wrong" in digest


BLS_PAGE = {"id": "bls-productivity", "url": "https://www.bls.gov/news.release/prod2.nr0.htm",
            "text_contains": "PRODUCTIVITY AND COSTS", "excerpt_after": "PRODUCTIVITY AND COSTS"}


def test_agency_release_and_usda_report_are_captured(tmp_path: Path):
    config = {"pages": [BLS_PAGE], "usda_reports": {"releases": {"wasde": "World Agricultural Supply and Demand Estimates"}}}
    result = collect(tmp_path, config, NOW, client=_client())

    assert [(row["source_id"], row["identity_status"]) for row in result.sources] == [("bls-productivity", "match"), ("usda-wasde", "match")]
    usda = result.sources[1]
    # The newest issue is taken whatever order the library lists them in.
    assert usda["url"].endswith("/2/wasde1126.txt") and usda["publication_time"] == "2026-11-10T12:00:00+00:00"
    saved = (tmp_path / usda["body_path"]).read_text(encoding="utf-8")
    assert "\r" not in saved and "   Nov     827.51    1110.36\n" in saved
    assert (tmp_path / usda["raw_body_path"]).read_bytes().count(b"\r\n") == 4
    digest = (tmp_path / "hard-evidence" / "digest.md").read_text(encoding="utf-8")
    assert "Third Quarter 2026, Preliminary - 2026 Q03 Results: Third Quarter 2026, Preliminary Nonfarm business sector labor productivity increased 3.6 percent" in digest
    assert 'released 2026-11-10T12:00:00+00:00; text file begins "WASDE - 677 - 8 November 2026"' in digest
    assert "which this capture did not read: https://esmis.nal.usda.gov/sites/default/release-files/2/wasde1126.pdf" in digest


def test_a_page_or_report_that_is_not_the_one_asked_for_is_flagged(tmp_path: Path):
    config = {
        "pages": [{**BLS_PAGE, "text_contains": "EMPLOYMENT SITUATION"}, {"id": "no-marker", "url": BLS_PAGE["url"]}],
        "usda_reports": {"releases": {"wasde": "Crop Production", "pdfonly": "Some Report"}},
    }
    result = collect(tmp_path, config, NOW, client=_client())

    assert [(row["source_id"], row["identity_status"]) for row in result.sources] == [
        ("bls-productivity", "mismatch"), ("no-marker", "mismatch"), ("usda-wasde", "mismatch")]
    assert result.not_captured == [{"source_id": "usda-pdfonly", "url": "https://esmis.nal.usda.gov/", "error": "unreadable response: ValueError"}]


def test_pages_in_an_older_encoding_keep_their_punctuation():
    from investment_os.radar_evidence import _decode

    assert _decode("JOB OPENINGS \u2013 SEPTEMBER".encode("cp1252")) == "JOB OPENINGS \u2013 SEPTEMBER"
    assert _decode("镍 \u2013 Ni".encode("utf-8")) == "镍 \u2013 Ni"


def test_strict_cli_exits_nonzero_when_a_source_is_missing(tmp_path: Path, monkeypatch, capsys):
    import investment_os.radar_evidence as module

    monkeypatch.setattr(module, "HttpClient", lambda **_kwargs: _client())
    config = tmp_path / "hard.yaml"
    config.write_text("pages:\n  - {id: blocked, url: 'https://example.gov/blocked', title_contains: x}\n", encoding="utf-8")
    args = ["radar", "collect", "--run-dir", str(tmp_path / "run"), "--config", str(config), "--now", NOW.isoformat()]

    assert main(args) == 0
    assert main([*args, "--strict"]) == 1
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["not_captured"] == ["blocked"]


def test_large_raw_responses_are_hashed_but_not_stored(tmp_path: Path, monkeypatch):
    import investment_os.radar_evidence as module

    monkeypatch.setattr(module, "RAW_KEEP_BYTES", 10)
    result = collect(tmp_path, {"pages": CONFIG["pages"]}, NOW, client=_client())

    row = result.sources[0]
    assert "raw_body_path" not in row and len(row["raw_sha256"]) == 64
    assert sorted(path.name for path in (tmp_path / "hard-evidence").iterdir()) == ["digest.md", "enso.txt", "hard-sources.json"]


def test_a_second_call_in_the_same_run_adds_to_the_first(tmp_path: Path):
    collect(tmp_path, {"fred": CONFIG["fred"], "pages": [{"id": "blocked", "url": "https://example.gov/blocked", "title_contains": "x"}]}, NOW, client=_client())
    first_sha = json.loads((tmp_path / "hard-evidence" / "hard-sources.json").read_text(encoding="utf-8"))["sources"][0]["sha256"]

    later = collect(tmp_path, {}, NOW, sec_tickers=["NET"], client=_client())

    assert [row["source_id"] for row in later.sources] == ["sec-net-8k-20261110", "sec-net-8k-20261110-doc1"]
    manifest = json.loads((tmp_path / "hard-evidence" / "hard-sources.json").read_text(encoding="utf-8"))
    assert [row["source_id"] for row in manifest["sources"]] == ["fred-dgs10", "sec-net-8k-20261110", "sec-net-8k-20261110-doc1"]
    assert manifest["sources"][0]["sha256"] == first_sha
    assert [row["source_id"] for row in manifest["not_captured"]] == ["blocked"]
    digest = (tmp_path / "hard-evidence" / "digest.md").read_text(encoding="utf-8")
    assert "DGS10 (US 10-year yield, percent): 4.88" in digest and "NET Cloudflare, Inc.: 8-K filed 2026-11-10" in digest and "- blocked:" in digest


def test_cli_needs_something_to_capture(tmp_path: Path):
    with pytest.raises(SystemExit):
        main(["radar", "collect", "--run-dir", str(tmp_path)])
