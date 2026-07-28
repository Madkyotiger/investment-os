from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChinaOfficialSourceTarget:
    authority: str
    topic: str
    source_url: str
    stable_machine_readable: bool
    blocker: str
    evidence_status: str = "source_target_only"
    queue_status: str = "open"


def official_source_targets() -> list[ChinaOfficialSourceTarget]:
    return [
        ChinaOfficialSourceTarget(
            "PBOC",
            "monetary policy releases and statistics",
            "https://www.pbc.gov.cn/en/3688006/index.html",
            False,
            "No stable documented public API has been verified; avoid brittle page scraping.",
        ),
        ChinaOfficialSourceTarget(
            "NBS",
            "national macroeconomic statistics releases",
            "https://www.stats.gov.cn/english/",
            False,
            "Public pages and data interfaces require endpoint-by-endpoint validation before automation.",
        ),
        ChinaOfficialSourceTarget(
            "CNINFO",
            "listed-company announcements",
            "https://www.cninfo.com.cn/new/index",
            False,
            "Access controls and undocumented request parameters make unattended retrieval brittle.",
        ),
        ChinaOfficialSourceTarget(
            "SSE",
            "Shanghai Stock Exchange announcements",
            "https://english.sse.com.cn/markets/equities/disclosure/",
            False,
            "Announcement retrieval path has not been verified as a stable documented API.",
        ),
        ChinaOfficialSourceTarget(
            "SZSE",
            "Shenzhen Stock Exchange announcements",
            "https://www.szse.cn/English/disclosures/index.html",
            False,
            "Announcement retrieval path has not been verified as a stable documented API.",
        ),
        ChinaOfficialSourceTarget(
            "HKEX",
            "HKEX listed-company news",
            "https://www1.hkexnews.hk/index.htm",
            False,
            "Search workflow is public but not verified here as a stable machine-readable endpoint.",
        ),
    ]
