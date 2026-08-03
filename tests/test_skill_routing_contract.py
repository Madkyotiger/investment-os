from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = ROOT / "skills" / "investment-research" / "SKILL.md"
FIXTURE_FILE = ROOT / "tests" / "fixtures" / "investment_research_routing.yaml"
TRIGGER_FIXTURE_FILE = (
    ROOT / "tests" / "fixtures" / "investment_research_chat_triggers.yaml"
)

ALLOWED_SURFACES = {
    "reader-chat",
    "reader-brief",
    "reader-plus-audit",
    "reader-deep-read",
    "research-pack",
    "evidence-ledger",
    "engineer-receipt",
    "refuse-and-reroute",
    "evidence-gap",
    "forwardable-brief",
}


def _frontmatter(text: str) -> dict[str, object]:
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    data = yaml.safe_load(match.group(1))
    assert isinstance(data, dict)
    return data


def _cases() -> list[dict[str, object]]:
    data = yaml.safe_load(FIXTURE_FILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    cases = data.get("cases")
    assert isinstance(cases, list)
    return cases


def _triggers() -> list[dict[str, object]]:
    data = yaml.safe_load(TRIGGER_FIXTURE_FILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    triggers = data.get("triggers")
    assert isinstance(triggers, list)
    return triggers


def test_routing_fixture_is_complete_and_unambiguous() -> None:
    cases = _cases()
    assert len(cases) >= 12

    ids = [case["id"] for case in cases]
    routes = [case["expected_route"] for case in cases]
    assert len(ids) == len(set(ids))
    assert len(routes) == len(set(routes))

    for case in cases:
        assert isinstance(case["prompt"], str) and case["prompt"].strip()
        assert case["expected_surface"] in ALLOWED_SURFACES
        assert isinstance(case["must_do"], list) and case["must_do"]
        assert isinstance(case["must_not_do"], list) and case["must_not_do"]


def test_skill_exposes_every_fixture_route_and_output_contract() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    assert metadata["version"] == "2.3.1"

    for case in _cases():
        route = case["expected_route"]
        surface = case["expected_surface"]
        assert f"`{route}`" in text, route
        assert f"`{surface}`" in text, surface

    required_contracts = {
        "A-share coverage is additive",
        "Reader surface",
        "Audit surface",
        "one phone screen",
        "brief first",
        "not found in this scan",
        "no event occurred",
        "anti-ai-writing",
        "Refuse categorically",
        "refusal based on authority boundary, never on missing data",
        "traceable source links or supplied source IDs",
        "same-day co-movement is not causal proof",
        "call a shared driver only when exposure and transmission evidence support it",
        "do not describe the event as driving, catalyzing, causing, or leading the market move",
        "跑投研简报",
        "只刷新投研读者版",
        "看详细版",
        "完整报一遍",
        "跑全市场简报",
        "本报告只用于信息整理、研究讨论和风险提示，不构成投资建议、交易建议或收益承诺。",
    }
    missing = sorted(fragment for fragment in required_contracts if fragment not in text)
    assert not missing, f"missing routing/output contracts: {missing}"

    stale_contract = "current runnable local pipeline is the AI-infrastructure pilot"
    assert stale_contract not in text


def test_chat_trigger_contract_preserves_execution_semantics() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")
    triggers = _triggers()
    assert len(triggers) == 5

    ids = [trigger["id"] for trigger in triggers]
    assert len(ids) == len(set(ids))

    for trigger in triggers:
        phrases = trigger["phrases"]
        fragments = trigger["required_fragments"]
        assert isinstance(phrases, list) and phrases
        assert isinstance(fragments, list) and fragments
        for phrase in phrases:
            assert f"`{phrase}`" in text, phrase
        for fragment in fragments:
            assert fragment in text, fragment
