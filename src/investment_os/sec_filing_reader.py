"""Read what an SEC filing itself states: the event items of an 8-K, and the
headline figures a 10-Q or 10-K reports in its own XBRL data.

The reader restates the filing. It does not say whether the event or the numbers
are good, expected, or priced in; that stays with the reader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

# SEC Form 8-K item numbers. The flag marks items that report a business event
# rather than a procedural or exhibit-only disclosure.
EIGHT_K_ITEMS: dict[str, tuple[str, bool]] = {
    "1.01": ("签订重大最终协议", True),
    "1.02": ("终止重大最终协议", True),
    "1.03": ("破产或接管", True),
    "1.05": ("重大网络安全事件", True),
    "2.01": ("完成资产收购或处置", True),
    "2.02": ("经营业绩与财务状况", True),
    "2.03": ("新增直接财务义务或表外安排下的义务", True),
    "2.04": ("触发财务义务加速或增加的事件", True),
    "2.05": ("退出或处置活动的相关成本", True),
    "2.06": ("重大减值", True),
    "3.01": ("收到退市通知或未满足持续上市规则", True),
    "3.02": ("未注册的股权证券发行", True),
    "3.03": ("证券持有人权利的重大变更", True),
    "4.01": ("更换审计师", True),
    "4.02": ("此前发布的财务报表不可再依赖", True),
    "5.01": ("控制权变更", True),
    "5.02": ("董事或高管的离任、任命与薪酬安排", True),
    "5.03": ("章程或细则修订、财年变更", False),
    "5.07": ("股东投票结果", False),
    "7.01": ("公平披露规则下的信息披露", False),
    "8.01": ("其他事件", False),
    "9.01": ("财务报表与附件", False),
}
_ITEM_PATTERN = re.compile(r"\bItem\s+(\d\.\d{2})\b", re.IGNORECASE)
_REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
)
# NetIncomeLoss is net income attributable to the parent company, before preferred dividends.
_NET_INCOME_TAGS = ("NetIncomeLoss",)
_EPS_TAGS = ("EarningsPerShareDiluted",)
_PERIOD_DAYS = {"10-Q": (80, 100), "10-K": (350, 380)}


@dataclass(frozen=True)
class EightKReading:
    items: tuple[str, ...]

    @property
    def substantive(self) -> bool:
        return any(EIGHT_K_ITEMS[item][1] for item in self.items)

    @property
    def lead_item(self) -> str:
        return next((item for item in self.items if EIGHT_K_ITEMS[item][1]), self.items[0])

    def describe(self) -> str:
        return "、".join(f"{EIGHT_K_ITEMS[item][0]}（第 {item} 项）" for item in self.items)


@dataclass(frozen=True)
class PeriodFact:
    current: float
    prior: float | None


@dataclass(frozen=True)
class PeriodicReading:
    period_end: str
    revenue: PeriodFact
    net_income: PeriodFact | None
    diluted_eps: PeriodFact | None


def read_8k_items(body_text: str) -> EightKReading | None:
    """Item headings found in the filing body, in order of first appearance."""
    found = dict.fromkeys(match for match in _ITEM_PATTERN.findall(body_text) if match in EIGHT_K_ITEMS)
    return EightKReading(tuple(found)) if found else None


def _period_fact(rows: list[Mapping[str, Any]], accession: str, form: str) -> tuple[str, PeriodFact] | None:
    low, high = _PERIOD_DAYS[form]
    in_filing: list[tuple[date, float]] = []
    for row in rows:
        if row.get("accn") != accession or "start" not in row or "end" not in row:
            continue
        try:
            start, end = date.fromisoformat(str(row["start"])), date.fromisoformat(str(row["end"]))
            value = float(row["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if low <= (end - start).days <= high:
            in_filing.append((end, value))
    if not in_filing:
        return None
    current_end, current = max(in_filing)
    prior = next(
        (value for end, value in in_filing if 355 <= (current_end - end).days <= 375),
        None,
    )
    return current_end.isoformat(), PeriodFact(current, prior)


def _first_fact(
    facts: Mapping[str, Any], tags: tuple[str, ...], unit: str, accession: str, form: str,
) -> tuple[str, PeriodFact] | None:
    for tag in tags:
        rows = ((facts.get(tag) or {}).get("units") or {}).get(unit)
        if isinstance(rows, list):
            found = _period_fact(rows, accession, form)
            if found:
                return found
    return None


def read_periodic_facts(company_facts: Mapping[str, Any], accession: str, form: str) -> PeriodicReading | None:
    """Revenue, net income attributable to the parent and diluted EPS, as this filing reports them for its own period and the year-ago period."""
    if form not in _PERIOD_DAYS:
        return None
    facts = (company_facts.get("facts") or {}).get("us-gaap")
    if not isinstance(facts, Mapping):
        return None
    revenue = _first_fact(facts, _REVENUE_TAGS, "USD", accession, form)
    if revenue is None:
        return None
    net_income = _first_fact(facts, _NET_INCOME_TAGS, "USD", accession, form)
    eps = _first_fact(facts, _EPS_TAGS, "USD/shares", accession, form)
    return PeriodicReading(
        period_end=revenue[0],
        revenue=revenue[1],
        net_income=net_income[1] if net_income and net_income[0] == revenue[0] else None,
        diluted_eps=eps[1] if eps and eps[0] == revenue[0] else None,
    )


def format_usd(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 100_000_000:
        return f"{magnitude / 100_000_000:,.2f} 亿美元"
    return f"{magnitude / 10_000:,.0f} 万美元"


def _year_over_year(fact: PeriodFact) -> str:
    if fact.prior is None or fact.prior <= 0:
        return ""
    change = (fact.current - fact.prior) / fact.prior * 100
    return f"，同比{'增长' if change >= 0 else '下降'} {abs(change):.1f}%"


def describe_periodic(reading: PeriodicReading) -> str:
    parts = [f"营收 {format_usd(reading.revenue.current)}{_year_over_year(reading.revenue)}"]
    if reading.net_income is not None:
        current, prior = reading.net_income.current, reading.net_income.prior
        text = f"归属于母公司的{'净利润' if current >= 0 else '净亏损'} {format_usd(current)}"
        if prior is not None:
            text += f"（上年同期{'净利润' if prior >= 0 else '净亏损'} {format_usd(prior)}）"
        parts.append(text)
    if reading.diluted_eps is not None:
        text = f"每股摊薄收益 {reading.diluted_eps.current:.2f} 美元"
        if reading.diluted_eps.prior is not None:
            text += f"（上年同期 {reading.diluted_eps.prior:.2f} 美元）"
        parts.append(text)
    return "；".join(parts)
