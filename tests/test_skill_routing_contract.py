from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = ROOT / "skills" / "investment-research" / "SKILL.md"
FIXTURE_FILE = ROOT / "tests" / "fixtures" / "investment_research_routing.yaml"

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
    assert metadata["version"] == "2.3.0"

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
    }
    missing = sorted(fragment for fragment in required_contracts if fragment not in text)
    assert not missing, f"missing routing/output contracts: {missing}"

    stale_contract = "current runnable local pipeline is the AI-infrastructure pilot"
    assert stale_contract not in text
