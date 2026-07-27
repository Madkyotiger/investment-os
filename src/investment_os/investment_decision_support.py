from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .source_verification_crosswalk import _clean, _parse_note
from .spike1_research_memo import EvidenceItem
from .us_china_pilot import scan_boundary, scan_external_note_quality


@dataclass
class ThemeRead:
    symbol: str
    label: str
    action: str
    plain_read: str
    evidence_line: str
    still_missing: str
    next_check: str
    names_to_watch: str
    role: str
    confidence: str


@dataclass
class InvestmentDecisionSupportResult:
    detailed_path: Path
    brief_path: Path
    quality_scan_path: Path


TECHNICAL_SMELL_MARKERS = [
    "evidence ledger",
    "source verification",
    "source-check",
    "source_check",
    "queue",
    "renderer",
    "schema",
    "dataos",
    "generated at",
    "category",
    "status",
    "p0",
    "p1",
    "csv",
    "json",
    ".md",
    "/mnt/",
    "uv run",
]

AI_WRITING_SMELL_MARKERS = [
    "这份东西",
    "它只回答",
    "先给判断",
    "为什么看：",
    "现在看到的证据：",
    "还差什么：",
    "当前判断：",
    "已有资料：",
    "关键缺口：",
    "下一步：",
    "可以先盯的名字：",
    "用来当底图的线索",
    "先别急的部分",
    "对实际研究的用法",
    "今天先看三件事",
    "一句话：",
    "下一步最有价值：",
]

THEME_ORDER = [
    "theme:memory_passives",
    "theme:datacenter_power",
    "theme:photonics_cpo",
    "theme:ai_infrastructure",
    "theme:physical_ai",
    "theme:physical_ai_supply_chain",
    "theme:market_attention_rotation",
]

NATURAL_LANGUAGE_REPLACEMENTS = {
    "Micron reports": "Micron 年报提到",
    "Vertiv says": "Vertiv 年报提到",
    "Broadcom says": "Broadcom 年报提到",
    "NVIDIA describes": "NVIDIA 年报描述",
    "NVIDIA says": "NVIDIA 年报提到",
    "Murata states": "Murata 投资者日资料提到",
    "Murata says": "Murata 投资者日资料提到",
    "Amazon reports": "Amazon 年报提到",
    "Amazon says": "Amazon 年报提到",
    "supplier filings": "供应商公告和年报",
    "segment revenue": "分部收入",
    "customer concentration": "客户集中度",
    "product disclosures": "产品披露",
    "shipment/capacity data": "出货和产能数据",
    "utility interconnect queues": "电网接入排队情况",
    "supplier backlog": "供应商订单",
    "deployment timing": "落地节奏",
    "optical-vendor": "光通信厂商",
    "optical vendor": "光通信厂商",
    "CPO delay claims": "CPO 延后说法",
    "capex guidance": "资本开支口径",
    "data center": "数据中心",
    "high-value data center markets": "高价值数据中心市场",
    "AI semiconductor solutions": "AI 芯片方案",
    "Ethernet silicon": "以太网芯片",
    "NICs": "网卡",
    "PHYs": "物理层芯片",
    "optical components": "光器件",
}


def _naturalize(text: str, limit: int | None = None) -> str:
    result = str(text or "")
    for old, new in NATURAL_LANGUAGE_REPLACEMENTS.items():
        result = result.replace(old, new)
    return _clean(result, limit)


THEME_PROFILES = {
    "theme:memory_passives": {
        "label": "内存 / 被动件",
        "action": "先深挖",
        "role": "最像下一轮可以落到公司和财务数据上的线索。",
        "evidence": "Micron 年报显示，数据中心内存需求已经影响收入和供给安排；Murata 的投资者资料也把 AI 服务器和电容、电源模块需求连在了一起。",
        "missing": "还不知道 HBM/DRAM 的紧张会持续多久、合同价格怎么走、毛利能不能真正受益。",
        "next": "补 HBM 产能、客户验证、ASP、库存和毛利资料，再对比 Micron、SK hynix、Samsung 与被动件同业。",
        "names": "Micron、Murata",
    },
    "theme:datacenter_power": {
        "label": "机房电力 / 散热",
        "action": "先深挖",
        "role": "AI 机房扩张绕不开电力、散热和机柜侧供电，这条线不只是芯片故事。",
        "evidence": "Vertiv 年报明确提到数据中心电力需求上升；Murata 的资料也提到服务器功耗上升、机柜侧备电和电源模块需求。",
        "missing": "还不知道真正卡住的是电网接入、变压器/开关设备、BBU 电池，还是热管理设备。也还不知道谁能拿到更好的利润。",
        "next": "补电网接入排队、变压器和开关设备订单、BBU 电池链、Vertiv/Eaton 订单和数据中心资本开支。",
        "names": "Vertiv、Murata",
    },
    "theme:photonics_cpo": {
        "label": "网络 / 光通信 / CPO",
        "action": "继续盯",
        "role": "方向有产业相关性，但市场争议还没被正式资料拆清楚。",
        "evidence": "Broadcom 年报能证明 AI 网络和光器件确实在相关链条里，但还不能说明 CPO 的落地节奏。",
        "missing": "CPO 是否延后、Meta 等大客户资本开支有没有变化、不同厂商的部署时间表，目前都还没拆清。",
        "next": "继续看 NVIDIA、Meta、Broadcom 和主要光通信厂商的电话会、年报和资本开支表述。",
        "names": "Broadcom、NVIDIA、Meta 与主要光通信厂商；先看部署节奏和资本开支口径。",
    },
    "theme:ai_infrastructure": {
        "label": "AI 基建总框架",
        "action": "当作底图",
        "role": "它说明问题不只在 GPU，但它本身不是一个足够细的投资切口。",
        "evidence": "NVIDIA 年报把 Blackwell 描述成一整套数据中心基础设施，不只是 GPU；同时也披露了供给和产能采购安排。",
        "missing": "这只能说明链条变长，不能说明哪个环节最紧、紧多久、谁赚钱。",
        "next": "把封装、内存、被动件、电力、网络和系统供应商逐层拆开，看产能、价格、交期、订单和毛利。",
        "names": "NVIDIA 是起点；下一步要顺着封装、内存、电力、网络和系统供应链拆。",
    },
    "theme:physical_ai": {
        "label": "Physical AI / 机器人落地",
        "action": "等经营数据",
        "role": "Amazon 的机器人和 AWS 供给紧张能证明应用场景存在，但还没证明谁能持续赚钱。",
        "evidence": "Amazon 年报说明仓库机器人规模已经很大，AWS 也仍有算力和电力供给压力。",
        "missing": "还没看到机器人投入如何稳定改善履约成本、单位效率和利润率。",
        "next": "把机器人数量、履约成本、自动化资本开支、配送速度和分部利润率放在一起看。",
        "names": "Amazon 可作为场景样本；下一步看履约成本、自动化投入、单位效率和利润率。",
    },
    "theme:physical_ai_supply_chain": {
        "label": "Physical AI 上游零部件",
        "action": "先放一放",
        "role": "故事有想象力，但公司收入、客户和毛利证据还没接上。",
        "evidence": "现在还没有足够正式资料把传感器、执行器、减速器、轴承、激光和电源电子这些零部件，连接到具体公司的收入弹性。",
        "missing": "缺供应商收入、客户关系、产品放量和毛利证据。没有这些，就只能算想象力，不算研究主线。",
        "next": "先找供应商年报、分部收入、客户集中度、产品披露、出货和产能数据。",
        "names": "先不急着列核心标的；先找传感器、执行器、减速器、轴承、激光、电源电子的公开收入证据。",
    },
    "theme:market_attention_rotation": {
        "label": "市场注意力轮动",
        "action": "只作提醒",
        "role": "这不是一个独立机会，更像提醒我们别把热度变化误读成供需变化。",
        "evidence": "它本身不是单一公司资料能证明的东西，只能用价格、成交、交期、订单和利润率一起交叉看。",
        "missing": "还不能判断某个瓶颈是真的缓解了，还是市场暂时不聊了。",
        "next": "把专家信号日期、价格反应、供应商交期、ASP、订单、资本开支、毛利和出货放进同一条时间线。",
        "names": "不对应单一公司；需要价格、成交、交期、价格、库存、订单和利润率一起看。",
    },
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _rows_to_items(rows: Iterable[dict[str, str]]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for row in rows:
        items.append(
            EvidenceItem(
                symbol=row.get("symbol", ""),
                category=row.get("category", ""),
                claim=row.get("claim", ""),
                value=row.get("value", ""),
                source=row.get("source", ""),
                as_of_date=row.get("as_of_date", ""),
                freshness=row.get("freshness", ""),
                status=row.get("status", ""),
                url=row.get("url", ""),
                note=row.get("note", ""),
            )
        )
    return items


def _best_source_line(items: list[EvidenceItem]) -> str:
    checked = [item for item in items if item.category.startswith("expert_source") and item.status == "ok"]
    partial = [item for item in items if item.category.startswith("expert_source") and item.status != "ok"]
    if checked:
        examples = []
        for item in checked[:2]:
            source = item.source.split(":", 1)[-1].strip() or item.source
            examples.append(f"{source}：{_naturalize(item.value, 90)}")
        return "；".join(examples)
    if partial:
        item = partial[0]
        source = item.source.split(":", 1)[-1].strip() or item.source
        return f"已有一条不完整资料：{source}，但它只能说明一部分。"
    signals = [item for item in items if item.category.startswith("expert_signal") or item.category == "expert_counter_signal"]
    if signals:
        return "目前主要还是公开讨论里的线索，正式资料还没跟上。"
    return "这一段还没有形成可用资料。"


def _missing_line(items: list[EvidenceItem], queue_rows: list[dict[str, str]]) -> str:
    queue_notes = [_naturalize(row.get("source_gap", ""), 130) for row in queue_rows if row.get("source_gap")]
    if queue_notes:
        return queue_notes[0]
    source_items = [item for item in items if item.category.startswith("expert_source")]
    for item in source_items:
        parsed = _parse_note(item)
        cannot = _naturalize(parsed.get("Cannot prove", ""), 130)
        if cannot:
            return cannot
    return "还缺能改变判断的下一层资料。"


def _next_check_line(items: list[EvidenceItem], queue_rows: list[dict[str, str]]) -> str:
    targets = [_naturalize(row.get("source_targets", ""), 160) for row in queue_rows if row.get("source_targets")]
    if targets:
        return targets[0]
    for item in items:
        parsed = _parse_note(item)
        action = _naturalize(parsed.get("Next action", ""), 160)
        if action:
            return action
    return "下一步补公司公告、财报电话会、供应商产能、价格和利润率资料。"


def _confidence(items: list[EvidenceItem]) -> str:
    source_items = [item for item in items if item.category.startswith("expert_source")]
    ok_count = sum(1 for item in source_items if item.status == "ok")
    missing_count = sum(1 for item in source_items if item.status == "missing")
    partial_count = sum(1 for item in source_items if item.status not in {"ok", "missing"})
    if ok_count >= 2 and missing_count == 0 and partial_count == 0:
        return "正式资料支持较多"
    if ok_count >= 1 and missing_count == 0:
        return "有资料支持，但还没定论"
    if missing_count > 0:
        return "证据还不够"
    return "还在观察层"


def build_theme_read(ledger_csv_path: Path, queue_csv_path: Path | None = None) -> list[ThemeRead]:
    ledger_rows = _read_csv(ledger_csv_path)
    queue_rows = _read_csv(queue_csv_path) if queue_csv_path else []
    items = _rows_to_items(ledger_rows)
    grouped: dict[str, list[EvidenceItem]] = {}
    for item in items:
        if item.symbol.startswith("theme:"):
            grouped.setdefault(item.symbol, []).append(item)
    queue_by_symbol: dict[str, list[dict[str, str]]] = {}
    for row in queue_rows:
        symbol = row.get("symbol", "")
        if symbol:
            queue_by_symbol.setdefault(symbol, []).append(row)

    symbols = [symbol for symbol in THEME_ORDER if symbol in grouped]
    symbols.extend(sorted(symbol for symbol in grouped if symbol not in symbols))
    reads: list[ThemeRead] = []
    for symbol in symbols:
        profile = THEME_PROFILES.get(symbol, {})
        label = profile.get("label", symbol.replace("theme:", ""))
        action = profile.get("action", "继续观察")
        role = profile.get("role", "先看资料是否能支撑到公司层面的收入和利润。")
        names = profile.get("names", "先补公司、客户和供应链资料，再列观察名单。")
        theme_items = grouped[symbol]
        reads.append(
            ThemeRead(
                symbol=symbol,
                label=label,
                action=action,
                plain_read=role,
                evidence_line=profile.get("evidence") or _best_source_line(theme_items),
                still_missing=profile.get("missing") or _missing_line(theme_items, queue_by_symbol.get(symbol, [])),
                next_check=profile.get("next") or _next_check_line(theme_items, queue_by_symbol.get(symbol, [])),
                names_to_watch=names,
                role=role,
                confidence=_confidence(theme_items),
            )
        )
    return reads


def _section_for_action(themes: list[ThemeRead], action: str) -> list[ThemeRead]:
    return [theme for theme in themes if theme.action == action]


def render_detailed_pack(themes: list[ThemeRead], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    deep = _section_for_action(themes, "先深挖")
    watch = _section_for_action(themes, "继续盯")
    wait = [theme for theme in themes if theme.action in {"等经营数据", "先放一放", "只作提醒"}]
    map_only = _section_for_action(themes, "当作底图")

    lines: list[str] = []
    lines.append("# AI 基建：研究时间先放哪")
    lines.append("")
    lines.append(f"资料口径：{generated_at.date().isoformat()}。这不是交易建议，只是把今天值得花精力的线索先排个顺序。")
    lines.append("")
    lines.append("我不会把这轮 AI 基建继续缩成 GPU 一个问题。GPU 还是起点，但真正值得往下拆的，是那些已经能落到公司收入、产能、价格和订单里的环节。按现在的资料看，内存 / 被动件和机房电力 / 散热最值得先做公司卡；网络 / 光通信 / CPO 有产业相关性，但争议还没拆清；Physical AI 上游零部件想象力不小，可收入和客户证据还没接上，暂时放后面。")
    lines.append("")
    if deep:
        lines.append("## 最先花时间的两条线")
        lines.append("")
        for theme in deep:
            lines.append(f"**{theme.label}**")
            lines.append(f"{theme.plain_read}{theme.evidence_line}但现在还不能急着往结论走：{theme.still_missing}我会先看 {theme.names_to_watch}，接着看：{theme.next_check}")
            lines.append("")
    if watch:
        lines.append("## 留在观察区的线")
        lines.append("")
        for theme in watch:
            lines.append(f"**{theme.label}**")
            lines.append(f"这条线不是没有价值，而是还没到能下判断的时候。{theme.evidence_line}{theme.still_missing}接下来{theme.next_check}")
            lines.append("")
    if map_only:
        lines.append("## 只能当底图，不能当机会")
        lines.append("")
        for theme in map_only:
            lines.append(f"**{theme.label}**")
            lines.append(f"{theme.plain_read}{theme.evidence_line}所以它的用法不是直接找标的，而是顺着链条继续拆：{theme.next_check}")
            lines.append("")
    if wait:
        lines.append("## 现在先别急")
        lines.append("")
        for theme in wait:
            lines.append(f"**{theme.label}**")
            lines.append(f"{theme.plain_read}主要问题是：{theme.still_missing}如果还要跟，就{theme.next_check}")
            lines.append("")
    lines.append("## 会改变判断的几个信号")
    lines.append("")
    lines.append("- 内存和被动件：HBM、DRAM、MLCC、DC-DC 模块如果出现更清楚的产能、价格、交期和毛利资料，才值得升级成具体公司深研。")
    lines.append("- 电力和散热：电网接入、机柜供电、BBU、电力设备和热管理订单如果继续被公司正式提到，这条线会更硬。")
    lines.append("- CPO / 光通信：NVIDIA、Meta、Broadcom 或主要光通信厂商要给出更清楚的部署节奏，争议才拆得开。")
    lines.append("- Physical AI 上游：看不到供应商收入、客户集中度、产品放量和利润率之前，不把它当主线。")
    lines.append("")
    lines.append("我会把这份输出当研究时间表用：先做内存 / 被动件、电力 / 散热两张公司卡；CPO 留在观察区；Physical AI 上游等证据。这样看 X、财报、研报和新闻时，不会被每个热词带着跑。")
    lines.append("")
    return "\n".join(lines)


def render_daily_brief(themes: list[ThemeRead], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    deep = _section_for_action(themes, "先深挖")
    watch = _section_for_action(themes, "继续盯")
    wait = [theme for theme in themes if theme.action in {"先放一放", "等经营数据"}]
    first_deep = "、".join(theme.label for theme in deep[:2]) or "内存 / 被动件、机房电力 / 散热"
    first_watch = watch[0].label if watch else "CPO / 光通信"
    first_wait = wait[0].label if wait else "Physical AI 上游零部件"

    lines: list[str] = []
    lines.append("# 今日投研简报｜AI 基建")
    lines.append("")
    lines.append(f"今天先放一个判断：AI 基建这轮，别只看 GPU。更值得先查的是{first_deep}；{first_watch} 继续放在观察区；{first_wait} 先别急着当主线。")
    lines.append("")
    for theme in deep[:2]:
        lines.append(f"- {theme.label}：{theme.role.rstrip('。')}，我会先看收入来源、产能、价格、订单和毛利。")
    if watch:
        theme = watch[0]
        lines.append(f"- {theme.label}：方向有产业相关性，但 {theme.still_missing.rstrip('。')}，现在还不适合下结论。")
    if wait:
        theme = wait[0]
        lines.append(f"- {theme.label}：还缺公司收入、客户和利润证据，暂时更像故事，不像主线。")
    lines.append("")
    lines.append("今天最该做的动作：先把内存 / 被动件和机房电力 / 散热各做一张公司卡。不要急着追新概念，先看数字能不能接上。")
    lines.append("")
    lines.append(f"资料口径：{generated_at.date().isoformat()}。不是交易建议。")
    lines.append("")
    return "\n".join(lines)


def scan_investment_output_quality(text: str) -> dict[str, int]:
    lower = text.lower()
    result = {f"technical:{marker}": lower.count(marker.lower()) for marker in TECHNICAL_SMELL_MARKERS}
    result.update({f"ai_style:{marker}": text.count(marker) for marker in AI_WRITING_SMELL_MARKERS})
    return result


def _combined_quality_scan(*texts: str) -> dict[str, int]:
    text = "\n".join(texts)
    result: dict[str, int] = {}
    result.update({f"boundary:{key}": value for key, value in scan_boundary(text).items()})
    result.update(scan_external_note_quality(text))
    result.update(scan_investment_output_quality(text))
    return result


def run(ledger_csv_path: Path, queue_csv_path: Path, out_dir: Path, generated_at: datetime | None = None) -> InvestmentDecisionSupportResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at or datetime.now(timezone.utc)
    themes = build_theme_read(ledger_csv_path, queue_csv_path)
    detailed = render_detailed_pack(themes, generated_at=generated_at)
    brief = render_daily_brief(themes, generated_at=generated_at)
    quality_scan = _combined_quality_scan(detailed, brief)
    nonzero = {marker: count for marker, count in quality_scan.items() if count}
    if nonzero:
        raise RuntimeError(f"Investment decision support quality scan failed: {nonzero}")

    detailed_path = out_dir / "investment_decision_support_pack.md"
    brief_path = out_dir / "daily_investment_brief.md"
    quality_scan_path = out_dir / "investment_decision_support_quality_scan.json"
    detailed_path.write_text(detailed, encoding="utf-8")
    brief_path.write_text(brief, encoding="utf-8")
    quality_scan_path.write_text(json.dumps(quality_scan, ensure_ascii=False, indent=2), encoding="utf-8")
    return InvestmentDecisionSupportResult(detailed_path=detailed_path, brief_path=brief_path, quality_scan_path=quality_scan_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render investor-useful detailed and mobile briefs from the research ledger.")
    parser.add_argument("--ledger", type=Path, default=Path("reports/us-china-pilot/us_china_evidence_ledger.csv"))
    parser.add_argument("--queue", type=Path, default=Path("reports/expert-signals/source_check_queue.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports/investment-decision-support"))
    args = parser.parse_args(argv)
    result = run(args.ledger, args.queue, out_dir=args.out)
    print(f"detailed={result.detailed_path}")
    print(f"brief={result.brief_path}")
    print(f"quality_scan={result.quality_scan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
