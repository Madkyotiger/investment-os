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
    assert metadata["version"] == "2.3.0"

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
