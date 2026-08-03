from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def load_replay(path: Path) -> dict[str, Any]:
    text = path.read_bytes().replace(b"\x00", b"").decode("utf-8", "replace")
    text = ANSI_RE.sub("", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"no JSON object found in {path}")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("replay payload must be a JSON object")
    return payload


def load_contract(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("contract must contain a cases list")
    return payload["cases"]


def validate_replay(
    contract_cases: list[dict[str, Any]], replay: dict[str, Any]
) -> list[str]:
    replay_cases = replay.get("cases")
    if not isinstance(replay_cases, list):
        return ["replay must contain a cases list"]

    by_id: dict[str, dict[str, Any]] = {}
    for case in replay_cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("id")
        if isinstance(case_id, str):
            by_id[case_id] = case
    errors: list[str] = []

    for contract in contract_cases:
        case_id = contract["id"]
        actual = by_id.get(case_id)
        if actual is None:
            errors.append(f"{case_id}: missing replay case")
            continue

        if actual.get("route") != contract["expected_route"]:
            errors.append(
                f"{case_id}: route {actual.get('route')!r} != "
                f"{contract['expected_route']!r}"
            )
        if actual.get("surface") != contract["expected_surface"]:
            errors.append(
                f"{case_id}: surface {actual.get('surface')!r} != "
                f"{contract['expected_surface']!r}"
            )

        output = actual.get("output")
        if not isinstance(output, str):
            errors.append(f"{case_id}: output must be a string")
            continue

        for pattern in contract.get("required_patterns", []):
            if re.search(pattern, output, flags=re.IGNORECASE | re.DOTALL) is None:
                errors.append(f"{case_id}: missing required pattern {pattern!r}")
        for pattern in contract.get("forbidden_patterns", []):
            if re.search(pattern, output, flags=re.IGNORECASE | re.DOTALL):
                errors.append(f"{case_id}: matched forbidden pattern {pattern!r}")

    expected_ids = {case["id"] for case in contract_cases}
    unexpected = sorted(set(by_id) - expected_ids)
    if unexpected:
        errors.append(f"unexpected replay cases: {unexpected}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a fixed investment-research model replay."
    )
    parser.add_argument("replay", type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("tests/fixtures/investment_research_output_cases.yaml"),
    )
    args = parser.parse_args()

    errors = validate_replay(load_contract(args.contract), load_replay(args.replay))
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("PASS investment-research output replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
