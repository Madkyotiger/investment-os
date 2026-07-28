from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .pipeline import FORBIDDEN_DECISION_WORDS
from .judgment_kernel import evidence_fingerprint, is_promotable
from .source_universe_intake import SourceCandidate, rank_source_candidates
from .topic_state import TopicChange, parse_generated_at
from .us_china_pilot import scan_boundary, scan_external_note_quality


@dataclass
class CXOProfile:
    profile_id: str
    label: str
    role: str
    decision_horizon: str
    business_exposure: list[str]
    asset_exposure: list[str]
    current_projects: list[str]
    trusted_source_preference: list[str]
    brief_style: str
    avoid: list[str]
    relevance_keywords: list[str]


@dataclass
class CXOBriefItem:
    candidate: SourceCandidate
    cxo_relevance: int
    cxo_reason: str

    @property
    def total_score(self) -> int:
        return self.candidate.total_score + self.cxo_relevance

    def to_row(self) -> dict[str, str | int]:
        row = self.candidate.to_row()
        row["cxo_relevance"] = self.cxo_relevance
        row["cxo_reason"] = self.cxo_reason
        row["cxo_total_score"] = self.total_score
        return row


def load_profile(path: Path, profile_id: str = "founder_operator") -> CXOProfile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    profile = (raw.get("profiles") or {}).get(profile_id)
    if not profile:
        raise KeyError(f"CXO profile not found: {profile_id}")
    return CXOProfile(
        profile_id=profile_id,
        label=profile.get("label", profile_id),
        role=profile.get("role", "CXO"),
        decision_horizon=profile.get("decision_horizon", "near term"),
        business_exposure=list(profile.get("business_exposure", [])),
        asset_exposure=list(profile.get("asset_exposure", [])),
        current_projects=list(profile.get("current_projects", [])),
        trusted_source_preference=list(profile.get("trusted_source_preference", [])),
        brief_style=profile.get("brief_style", "phone-screen brief"),
        avoid=list(profile.get("avoid", [])),
        relevance_keywords=list(profile.get("relevance_keywords", [])),
    )


def _load_candidates(path: Path) -> list[SourceCandidate]:
    if not path.exists():
        return []
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    candidates: list[SourceCandidate] = []
    for row in rows:
        candidates.append(
            SourceCandidate(
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
                source_authority=int(row.get("source_authority") or 1),
                freshness=int(row.get("freshness") or 1),
                evidence_change=int(row.get("evidence_change") or 1),
                magnitude=int(row.get("magnitude") or 1),
                novelty=int(row.get("novelty") or 1),
                decision_usefulness=int(row.get("decision_usefulness") or 1),
                portfolio_relevance=int(row.get("portfolio_relevance") or 1),
                confidence=row.get("confidence", ""),
                next_check=row.get("next_check", ""),
                kill_signal=row.get("kill_signal", ""),
                cannot_prove=row.get("cannot_prove", ""),
                thesis_key=row.get("thesis_key", ""),
                research_question=row.get("research_question", ""),
                thesis_impact=row.get("thesis_impact", "unknown"),
                counter_explanation=row.get("counter_explanation", ""),
                next_primary_source=row.get("next_primary_source", ""),
                evidence_status=row.get("evidence_status", ""),
                geography=row.get("geography", ""),
                evidence_digest=row.get("evidence_digest", ""),
                observed_value=row.get("observed_value", ""),
                retrieved_at=row.get("retrieved_at", ""),
                body_read_status=row.get("body_read_status", ""),
                content_hash=row.get("content_hash", ""),
                freshness_status=row.get("freshness_status", ""),
                freshness_threshold_days=int(float(row.get("freshness_threshold_days") or 0)),
            )
        )
    return candidates


def score_cxo_relevance(candidate: SourceCandidate, profile: CXOProfile) -> tuple[int, str]:
    text = " ".join(
        [
            candidate.title,
            candidate.summary,
            candidate.themes,
            candidate.tickers,
            candidate.research_question,
            candidate.next_primary_source,
        ]
    ).lower()
    keyword_hits = [kw for kw in profile.relevance_keywords if kw.lower() in text]
    exposure_hits = [item for item in profile.business_exposure + profile.asset_exposure if any(part.lower() in text for part in item.replace("/", " ").split())]
    project_hits = [item for item in profile.current_projects if any(part.lower() in text for part in item.replace("/", " ").split())]
    score = 1
    if keyword_hits:
        score += min(2, len(keyword_hits))
    if exposure_hits:
        score += 1
    if project_hits:
        score += 1
    if candidate.lane in {"macro_regime", "company_events", "sector_theme_discovery"}:
        score += 1
    score = max(1, min(5, score))
    if keyword_hits:
        reason = "关联到 " + " / ".join(keyword_hits[:4])
    elif exposure_hits:
        reason = "关联到个人投资兴趣或资产观察范围"
    else:
        reason = "只作市场背景"
    return score, reason


def build_cxo_brief_items(
    candidates: list[SourceCandidate],
    profile: CXOProfile,
    max_items: int = 5,
    topic_changes: list[TopicChange] | None = None,
) -> list[CXOBriefItem]:
    meaningful_ids: set[str] | None = None
    if topic_changes is not None:
        meaningful_ids = {change.item_id for change in topic_changes if change.changed_since_last_push}

    items: list[CXOBriefItem] = []
    seen_theses: set[str] = set()
    seen_fingerprints: set[str] = set()
    blocked_statuses = {
        "primary_metadata_only",
        "primary_body_retrieved",
        "source_target_only",
        "stale",
        "unavailable",
        "mixed_sources",
    }
    for candidate in candidates:
        if candidate.evidence_status in blocked_statuses or not is_promotable(candidate.to_row()):
            continue
        if meaningful_ids is not None and candidate.item_id not in meaningful_ids:
            continue
        if candidate.thesis_key in seen_theses:
            continue
        fingerprint = evidence_fingerprint(candidate.to_row())
        if fingerprint in seen_fingerprints:
            continue
        relevance, reason = score_cxo_relevance(candidate, profile)
        if relevance <= 1 and candidate.decision_usefulness < 4:
            continue
        seen_theses.add(candidate.thesis_key)
        seen_fingerprints.add(fingerprint)
        items.append(CXOBriefItem(candidate=candidate, cxo_relevance=relevance, cxo_reason=reason))
    return sorted(
        items,
        key=lambda item: (
            item.cxo_relevance,
            item.candidate.decision_usefulness,
            item.candidate.evidence_change,
            item.candidate.source_authority,
            item.candidate.portfolio_relevance,
        ),
        reverse=True,
    )[: min(max_items, 5)]


def render_coverage_receipt(
    candidates: list[SourceCandidate],
    topic_changes: list[TopicChange] | None = None,
) -> str:
    unique: dict[str, SourceCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.thesis_key or candidate.item_id, candidate)
    meaningful_keys = {
        change.thesis_key or change.item_id
        for change in (topic_changes or [])
        if change.changed_since_last_push
    }

    def clause(geography: str, label: str) -> str:
        covered = [candidate for candidate in unique.values() if candidate.geography == geography]
        if not covered:
            return f"{label}覆盖还没有形成可核验候选"
        meaningful = sum(1 for candidate in covered if (candidate.thesis_key or candidate.item_id) in meaningful_keys)
        if meaningful:
            return f"{label}已检查 {len(covered)} 条研究线，{meaningful} 条达到变化门槛"
        return f"{label}已检查 {len(covered)} 条研究线，没有足够强的变化"

    return "覆盖回执：" + "；".join([clause("US", "美国"), clause("China", "中国")]) + "。"


def _cn_lane(lane: str) -> str:
    return {
        "macro_regime": "宏观阀门",
        "company_events": "公司事件",
        "sector_theme_discovery": "产业主题",
        "market_action": "市场动作",
        "expert_and_media_signals": "专家/媒体线索",
        "portfolio_watchlist": "观察名单",
    }.get(lane, lane)


TITLE_REPLACEMENTS = {
    "China market breadth check is available but cross-source reconciliation is incomplete": "中国市场广度已有单源快照，但二源核验还没完成",
    "Memory/passives look like the next AI infrastructure bottleneck to verify": "内存和被动件正在变成 AI 基建下一层瓶颈，需要尽快核验",
    "Data-center power and cooling are moving from engineering constraint to market variable": "数据中心电力和散热，正在从工程约束变成市场变量",
    "financial snapshot sets the baseline for the coming earnings check": "财务快照决定下一轮财报该查什么",
    "market context changed enough to keep in the daily map": "市场背景变化足够大，今天要放进判断底图",
    "Treasury yield curve should anchor duration-sensitive equity interpretation": "美债收益率曲线要作为长久期资产判断的底盘",
    "Fed calendar is the primary macro trigger map for rate-path risk": "Fed 日程是判断利率路径风险的主触发器",
    "has SEC identity available for primary-source filing checks": "已完成 SEC 身份映射，可以进入一手 filing 检查",
    "FRED yield curve live snapshot is available for rate-sensitive equity checks": "FRED 美债收益率曲线已有实时快照，可以核验利率敏感资产",
    "Market proxy move is led by": "市场代理资产今日波动领头的是",
    "one-day change": "单日变化",
    "latest SEC filing is": "最新 SEC filing 是",
    "primary filing body was retrieved": "一手 filing 正文已取得",
    "watchlist is active for CXO relevance routing": "观察名单已进入 CXO 相关性路由",
}

TEXT_REPLACEMENTS = {
    "If AKShare and Tushare disagree materially, keep the China move as an unresolved data issue": "AKShare 与 Tushare 如果明显不一致，就把中国市场变化保留为待解决的数据问题",
    "that CMBU revenue benefited from shifting DRAM supply to meet strong demand in high-value data center markets; it also discloses CDBU revenue growth driven by data center DRAM/NAND pricing and SSD demand": "CMBU 收入受益于公司把 DRAM 供应转向需求强劲的高价值数据中心市场；CDBU 收入增长则来自数据中心 DRAM/NAND 的价格和 SSD 需求",
    "Yield levels alone do not prove equity direction or sector causality": "仅凭收益率水平，不能判断股市方向或行业因果",
    "Micron reports": "Micron 年报提到",
    "Vertiv says": "Vertiv 年报提到",
    "Latest annual revenue": "最新年收入",
    "Latest annual operating income": "最新年营业利润",
    "Latest annual net income": "最新年净利润",
    "Gross Margin": "毛利率",
    "Read the next earnings release, call transcript, capex guidance and FCF bridge": "去读下一份财报、电话会、资本开支口径和自由现金流变化",
    "Map the theme to revenue, orders, capex, pricing and margin evidence at company level": "把它落到公司层面的收入、订单、资本开支、价格和毛利证据上",
    "Downgrade if company filings and orders do not confirm the bottleneck narrative": "公司公告和订单不能继续支持瓶颈叙事",
    "If current financials are stale or restated, refresh before using in a CXO brief": "当前财务数据过期或被重述",
    "Compare against yields, USD and sector ETF leadership before interpreting single-name moves": "先对照利率、美元和行业 ETF 强弱，再解释单家公司变化",
    "If follow-up price and source data stop confirming the move, downgrade to background context": "后续价格和来源数据不再确认这个变化",
    "data center": "数据中心",
    "high-value": "高价值",
    "revenue": "收入",
    "demand": "需求",
    "power demand": "电力需求",
    "power 需求": "电力需求",
    "advanced power and thermal management solutions": "高阶供电和热管理方案",
    "is surging in the U.S. and describes work on": "在美国快速上升，同时公司正在推进",
    "for future": "服务未来",
    "needs": "需求",
    "future data center needs": "未来数据中心需求",
    "Treasury yield data is the primary reference for rate pressure on high-duration growth and AI-infrastructure financing assumptions": "美债收益率是判断长久期成长股和 AI 基建融资成本压力的主参考",
    "Pull latest 2Y/10Y/30Y yields and compare with TLT and growth-sector relative strength": "拉取最新 2Y/10Y/30Y 收益率，并和 TLT、成长板块相对强弱对照",
    "If yields are stale or unavailable, do not explain equity moves with rates": "收益率数据过期或不可用时，不用利率解释股价变化",
    "The Fed meeting calendar is the official source for upcoming policy dates; use it before interpreting rate-sensitive equity moves": "Fed 会议日程是政策日期的一手来源；解释利率敏感资产前先看它",
    "Fetch the next FOMC date, statement, minutes and dot-plot changes before writing rate-path conclusions": "先抓下一次 FOMC 日期、声明、纪要和点阵图变化，再写利率路径判断",
    "FRED latest Treasury constants": "FRED 最新美债利率",
    "US Treasury 2-Year Constant Maturity Rate": "美国国债 2 年期收益率",
    "US Treasury 10-Year Constant Maturity Rate": "美国国债 10 年期收益率",
    "US Treasury 30-Year Constant Maturity Rate": "美国国债 30 年期收益率",
    "10Y-2Y spread": "10Y-2Y 利差",
    "Compare yield move with TLT/QQQ/IWM and earnings multiple compression before explaining equity moves": "先把收益率变化和 TLT、QQQ、IWM 以及估值压缩放在一起看，再解释股价变化",
    "If FRED values are stale or market proxies disagree, keep rates as background rather than causal explanation": "如果 FRED 数值过期，或市场代理资产不配合，只把利率当背景，不当因果解释",
    "Read the filing body and transcript before turning metadata into a business conclusion": "先读 filing 正文和电话会记录，再把 metadata 变成经营判断",
    "If latest filing is routine or unrelated to capex/收入/risk, downgrade it from the CXO brief": "如果最新 filing 只是例行披露，或和资本开支、收入、风险无关，就从 CXO brief 降级",
    "SEC recent submissions": "SEC 最新披露",
    "SEC recent submissions show": "SEC 最新披露显示",
    "SEC filing body retrieved for": "SEC filing 正文已取得：",
    "interpretation remains blocked pending relevant-section review": "仍需阅读相关章节后才能形成解释",
    "Read the relevant business, risk, MD&A, and event sections before stating an implication": "先阅读经营、风险、管理层讨论与事件章节，再判断披露含义",
    "Body retrieval and hashing do not prove a business implication until relevant sections are read": "只取得并校验正文，不能在读完相关章节前证明经营含义",
    "If body retrieval or section extraction is incomplete, do not create a business interpretation": "如果正文取得或章节提取不完整，不形成经营解释",
    "latest filing": "最新 filing",
    "dated": "日期",
    " at ": "，单日 ",
    " on ": " 日期 ",
    "metadata": "元数据",
    "Use market proxy moves only after cross-checking the quote source and matching them against rates, dollar and sector leadership": "先做行情二源校验，再和利率、美元、行业强弱一起看",
    "If quote sources are stale, unavailable, or materially inconsistent, downgrade market-action commentary": "如果行情源过期、不可用，或二源明显不一致，就降级市场动作解读",
    "Price movement does not prove the cause of the move": "价格变化不能证明变化原因",
}

WORD_REPLACEMENTS = {
    "rates": "利率",
    "earnings": "盈利",
    "capex": "资本开支",
    "cloud": "云服务",
    "margin": "利润率",
    "cash flow": "现金流",
    "semiconductor": "半导体",
    "power": "电力",
    "beta": "贝塔",
    "close": "收盘",
    "1D": "1 日",
    "60D": "60 日",
}


def _zh(text: str) -> str:
    result = str(text or "")
    for old, new in TITLE_REPLACEMENTS.items():
        result = result.replace(old, new)
    for old, new in TEXT_REPLACEMENTS.items():
        result = result.replace(old, new)
    for old, new in WORD_REPLACEMENTS.items():
        result = re.sub(rf"\b{re.escape(old)}\b", new, result, flags=re.IGNORECASE)
    result = re.sub(
        r"(?<![A-Za-z])([0-9]+(?:\.[0-9]+)?)B\b",
        lambda match: f"{(Decimal(match.group(1)) * 10).normalize():f} 亿",
        result,
    )
    result = re.sub(r"([0-9]+(?:\.[0-9]+)?)pp\b", r"\1 个百分点", result, flags=re.IGNORECASE)
    result = result.replace(" show ", " 显示 ").replace(" 单日变化", "")
    return result


def _plain_summary(candidate: SourceCandidate) -> str:
    if candidate.source_type == "primary_macro_fred_yields_live":
        return _zh(candidate.summary)
    if candidate.source_type == "market_proxy_prices_live":
        return _zh(candidate.summary)
    if candidate.source_type == "primary_sec_recent_filing":
        return _zh(candidate.summary)
    if candidate.source_type == "primary_macro_rates":
        return "美债收益率是一手宏观锚点，用来核验长久期成长股、AI 基建融资成本和 TLT/QQQ/IWM 相对变化。"
    if candidate.source_type == "primary_macro_calendar":
        return "Fed 会议日程是一手政策触发器，用来核验市场对降息、美元和风险偏好的定价是否过度提前。"
    if candidate.lane == "macro_regime":
        return _zh(candidate.summary)
    return _zh(candidate.summary)


def _clean_cn_punctuation(text: str) -> str:
    return (
        text.replace(".。", "。")
        .replace(".，", "，")
        .replace(" .", "。")
        .replace("？。", "？")
        .replace("！。", "！")
    )


def _load_topic_changes(path: Path | None) -> list[TopicChange]:
    if not path or not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [TopicChange(**row) for row in rows]


def render_cxo_brief(
    items: list[CXOBriefItem],
    profile: CXOProfile,
    generated_at: datetime | None = None,
    topic_changes: list[TopicChange] | None = None,
    coverage_receipt: str = "",
) -> str:
    generated_at = generated_at or datetime.now(ZoneInfo("Asia/Shanghai"))
    local_date = generated_at.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    if not items:
        lines = [
            "# 个人投研简报",
            "",
            f"{local_date} 没有足够强的变化值得推送。沿用上次判断，不拿例行披露或市场背景凑数。",
        ]
        lines.extend(["", "只用于个人投资研究与风险判断，不是交易建议。", ""])
        return "\n".join(lines)

    lines: list[str] = ["# 个人投研快扫", ""]
    evidence_labels = {
        "primary_body_read": "一手正文已读",
        "primary_body_retrieved": "一手正文已获取，尚未完成相关段落阅读",
        "cross_checked_data": "二源核验数据",
        "single_source_data": "单源数据",
    }
    freshness_labels = {"current": "当前", "stale": "过期"}
    for item in items[:5]:
        cand = item.candidate
        title = _zh(cand.title).rstrip("。.")
        summary = _plain_summary(cand)[:180].rstrip("。.")
        question = _zh(cand.research_question).rstrip("。.")
        counter = _zh(cand.counter_explanation).rstrip("。.")
        next_source = _zh(cand.next_primary_source).rstrip("。.")
        kill_signal = _zh(cand.kill_signal).rstrip("。.")
        if kill_signal.startswith("如果"):
            kill_signal = kill_signal[2:]

        lines.extend([f"## {title}", "", _clean_cn_punctuation(f"{summary}。")])
        second_paragraph: list[str] = []
        if question:
            second_paragraph.append(question if question.endswith(("？", "！")) else f"{question}。")
        if counter:
            second_paragraph.append(f"另一个需要保留的解释是{counter}。")
        if next_source:
            second_paragraph.append(f"接下来用{next_source}核验。")
        if kill_signal:
            if kill_signal.endswith("下调判断") or kill_signal.endswith("应下调"):
                second_paragraph.append(f"若{kill_signal}。")
            else:
                second_paragraph.append(f"若{kill_signal}，当前判断应下调。")
        if second_paragraph:
            lines.extend(["", _clean_cn_punctuation("".join(second_paragraph))])
        if cand.source_url:
            lines.extend(["", f"[来源]({cand.source_url})"])
        evidence_label = evidence_labels.get(cand.evidence_status, cand.evidence_status)
        freshness_label = freshness_labels.get(cand.freshness_status, cand.freshness_status or "未知")
        lines.extend(["", f"证据状态：{evidence_label}；新鲜度：{freshness_label}；资料日期：{cand.as_of_date}。"])
        lines.append("")

    lines.append(f"资料截至：{local_date}。只用于个人投资研究与风险判断，不是交易建议。")
    lines.append("")
    return "\n".join(lines)


def scan_cxo_brief_quality(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    result.update({f"boundary:{key}": value for key, value in scan_boundary(text).items()})
    lower = text.lower()
    for word in FORBIDDEN_DECISION_WORDS:
        if word.isascii():
            count = len(re.findall(rf"(?<![A-Za-z0-9_-]){re.escape(word.lower())}(?![A-Za-z0-9_-])", lower))
        else:
            count = text.count(word)
        result[f"decision_boundary:{word}"] = count
    result.update(scan_external_note_quality(text))
    text_without_links = re.sub(r"\[[^\]]*\]\([^)]+\)", " ", text)
    text_without_links = re.sub(r"https?://\S+", " ", text_without_links)
    lower_without_links = text_without_links.lower()
    internal_markers = ["/mnt/", "uv run", "evidence ledger", "source verification", "renderer", "schema", "csv", "json", "dataos"]
    result.update({f"internal:{marker}": lower_without_links.count(marker.lower()) for marker in internal_markers})
    audience_misframes = ["问团队", "公司预算", "供应商选择", "管理判断", "覆盖回执"]
    result.update({f"audience_misframe:{marker}": text.count(marker) for marker in audience_misframes})
    allowed_english = {
        "ai", "aapl", "akshare", "alphabet", "amd", "amzn", "cdbu", "cmbu", "cloud", "cpu", "dram", "etf", "fed", "filing", "fomc",
        "form", "fred", "gcp", "google", "gpu", "hpc", "intel", "iwm", "micron", "nand", "nvidia",
        "googl", "msft", "nvda", "qqq", "sec", "smh", "spy", "ssd", "tlt", "tpu", "tsmc", "tushare", "usd", "vertiv", "vrt", "workspace",
        "xlk", "yoy", "qoq",
    }
    english_tokens = re.findall(r"\b[A-Za-z][A-Za-z-]{2,}\b", text_without_links)
    result["mixed_english:prose_tokens"] = sum(
        1
        for token in english_tokens
        if token.lower() not in allowed_english and not (token.isupper() and 1 <= len(token) <= 5)
    )
    ai_markers = [
        "为什么看：",
        "现在看到的证据：",
        "下一步：",
        "一句话：",
        "今天先看三件事",
        "今天最值得你看一眼",
        "发生了什么",
        "这意味着什么",
        "接下来只看",
        "下一次只看",
        "对个人投资研究",
        "需要继续回答的是：",
        "反方解释是：",
        "下一次重点看",
    ]
    result.update({f"ai_style:{marker}": text.count(marker) for marker in ai_markers})
    return result


def write_cxo_outputs(
    items: list[CXOBriefItem],
    profile: CXOProfile,
    out_dir: Path,
    generated_at: datetime | None = None,
    topic_changes: list[TopicChange] | None = None,
    candidates: list[SourceCandidate] | None = None,
) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage_receipt = render_coverage_receipt(candidates or [item.candidate for item in items], topic_changes)
    brief = render_cxo_brief(
        items,
        profile,
        generated_at=generated_at,
        topic_changes=topic_changes,
        coverage_receipt=coverage_receipt,
    )
    quality = scan_cxo_brief_quality(brief)
    nonzero = {key: value for key, value in quality.items() if value}
    if nonzero:
        raise RuntimeError(f"CXO brief quality scan failed: {nonzero}")
    brief_path = out_dir / "cxo_daily_brief.md"
    ranked_path = out_dir / "cxo_ranked_candidates.json"
    quality_path = out_dir / "cxo_brief_quality_scan.json"
    brief_path.write_text(brief, encoding="utf-8")
    ranked_path.write_text(json.dumps([item.to_row() for item in items], ensure_ascii=False, indent=2), encoding="utf-8")
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    return brief_path, ranked_path, quality_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a personal-investment brief for a financially sophisticated reader from ranked source candidates.")
    parser.add_argument("--candidates", type=Path, default=Path("reports/source-universe/source_universe_candidates.csv"))
    parser.add_argument("--profile", type=Path, default=Path("configs/cxo_profiles.yaml"))
    parser.add_argument("--profile-id", default="founder_operator")
    parser.add_argument("--topic-changes", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("reports/cxo-intelligence"))
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--generated-at", default="", help="ISO timestamp for reproducible historical samples.")
    args = parser.parse_args(argv)

    profile = load_profile(args.profile, args.profile_id)
    generated_at = parse_generated_at(args.generated_at)
    candidates = rank_source_candidates(_load_candidates(args.candidates))
    topic_changes = _load_topic_changes(args.topic_changes)
    items = build_cxo_brief_items(
        candidates,
        profile,
        max_items=args.max_items,
        topic_changes=topic_changes if args.topic_changes else None,
    )
    brief_path, ranked_path, quality_path = write_cxo_outputs(
        items,
        profile,
        args.out,
        generated_at=generated_at,
        topic_changes=topic_changes,
        candidates=candidates,
    )
    print(f"cxo_brief={brief_path}")
    print(f"cxo_ranked_candidates={ranked_path}")
    print(f"cxo_quality_scan={quality_path}")
    print(f"cxo_items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
