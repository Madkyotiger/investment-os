from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "investment-research"
SKILL_FILE = SKILL_DIR / "SKILL.md"


def _frontmatter(text: str) -> dict[str, object]:
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    data = yaml.safe_load(match.group(1))
    assert isinstance(data, dict)
    return data


def test_investment_research_skill_package_is_complete() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    assert metadata["name"] == "investment-research"
    assert metadata["version"] == "2.3.3"

    linked_paths = set(
        re.findall(r"`((?:references|templates)/[^`]+\.md)`", text)
    )
    assert linked_paths
    external_links = {"templates/cxo-financial-brief.md"}
    missing = sorted(
        path
        for path in linked_paths
        if path not in external_links and not (SKILL_DIR / path).is_file()
    )
    assert not missing, f"missing linked skill files: {missing}"

    package_assets = {
        str(path.relative_to(SKILL_DIR))
        for directory in ("references", "templates")
        for path in (SKILL_DIR / directory).glob("*.md")
    }
    unlinked = sorted(package_assets - linked_paths)
    assert not unlinked, f"unlinked skill assets: {unlinked}"

    body = text.split("\n---\n", maxsplit=1)[1]
    assert len(body.split()) <= 5_000


def test_retired_skill_slug_is_absent_from_package() -> None:
    retired = "investment" + "-research-systems"
    for path in SKILL_DIR.rglob("*.md"):
        assert retired not in path.read_text(encoding="utf-8"), path


def test_public_skill_has_no_private_runtime_owner_assumptions() -> None:
    forbidden = {
        "C 超",
        "Je" + "f",
        "local DataOS",
        "Current/private",
        "private-state",
    }
    for path in SKILL_DIR.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        leaked = sorted(token for token in forbidden if token in text)
        assert not leaked, f"private runtime assumptions in {path}: {leaked}"


def test_absorbed_research_procedures_have_positive_and_negative_routes() -> None:
    """Documentation contracts, not proof of new collector/replay behavior."""
    main = SKILL_FILE.read_text(encoding="utf-8")
    for trigger in (
        "Before historical reconstruction, load",
        "before filing retrieval/claim extraction, load",
        "for an explicit COT positioning question, load",
        "not automatic collectors or new execution authority",
    ):
        assert trigger in main

    cases = {
        "judgment-kernel-and-historical-replay.md": (
            "latest applicable revision published by the cutoff",
            "Different institutions' estimates coexist",
            "Capture/verification timestamps do not prove lesson-creation time",
            "observation_end",
            "vintage_dates",
            "live freshness classification is not a historical selector",
        ),
        "source-bounded-filing-claim-cards.md": (
            "Complete the requested scope",
            "Incomplete responses remain `partial`",
            "never forward credentials to an arbitrary URL",
            "Cache by source, document version and requested scope",
            "Metadata locates a file; it does not prove the body was read",
            "not a claim that a connector or cache has been implemented",
        ),
        "operational-pitfalls-and-verification.md": (
            "## On-demand CFTC COT corroboration",
            "not a default subscription",
            "A schedule is not an actual upload receipt",
            "Legacy non-commercial is not the same category",
            "not zero net positions",
            "Do not convert contract units into physical barrels/day",
        ),
    }
    for filename, fragments in cases.items():
        text = (SKILL_DIR / "references" / filename).read_text(encoding="utf-8")
        for fragment in fragments:
            assert fragment in text, (filename, fragment)
