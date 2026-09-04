from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from investment_os.cli import main
from investment_os.source_catalog import (
    SourceCatalogError,
    load_source_catalog,
    resolve_source_plan,
    validate_source_catalog,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "configs" / "public_source_catalog.json"
REQUEST_PATH = ROOT / "configs" / "source_request.sample.yaml"


def test_public_source_catalog_contains_shared_sources_and_is_on_demand_only():
    catalog = load_source_catalog(CATALOG_PATH)

    assert catalog["dispatch_mode"] == "on_demand_only"
    assert len(catalog["sources"]) == 15
    assert sum(source["kind"] == "expert" for source in catalog["sources"]) == 9
    assert sum(source["kind"] == "media" for source in catalog["sources"]) == 6
    assert all(source["source_role"] == "discovery_not_fact_authority" for source in catalog["sources"])


def test_source_plan_uses_reader_need_and_excludes_explicit_only_sources_by_default():
    catalog = load_source_catalog(CATALOG_PATH)
    request = yaml.safe_load(REQUEST_PATH.read_text(encoding="utf-8"))
    plan = resolve_source_plan(catalog, request)

    selected = plan["selected_sources"]
    selected_ids = {source["source_id"] for source in selected}
    assert selected
    assert not {
        "expert-martin-armstrong",
        "expert-andy-schectman",
        "expert-j-michael-oliver",
    } & selected_ids
    assert all(source["matched_topics"] for source in selected)
    assert all(source["matched_viewpoint_roles"] for source in selected)
    assert all(1 <= len(source["channels"]) <= request["limits"]["max_channels_per_source"] for source in selected)
    assert all(
        channel["access_state"] in request["access"]["allowed_access_states"]
        for source in selected
        for channel in source["channels"]
    )
    assert plan["fact_authority_required"] is True


def test_explicit_only_source_requires_both_permission_and_named_include():
    catalog = load_source_catalog(CATALOG_PATH)
    request = yaml.safe_load(REQUEST_PATH.read_text(encoding="utf-8"))
    request["decision"]["topics"] = ["technical_structure"]
    request["decision"]["geographies"] = ["global"]
    request["decision"]["viewpoint_roles"] = ["discovery"]
    request["access"]["include_source_ids"] = ["expert-j-michael-oliver"]

    blocked = resolve_source_plan(catalog, request)
    assert "expert-j-michael-oliver" not in {
        source["source_id"] for source in blocked["selected_sources"]
    }

    request["access"]["allow_explicit_need_only"] = True
    allowed = resolve_source_plan(catalog, request)
    selected = allowed["selected_sources"]
    assert selected[0]["source_id"] == "expert-j-michael-oliver"
    assert selected[0]["selection_reason"] == "explicit_include"


def test_source_request_fails_closed_without_access_permission():
    catalog = load_source_catalog(CATALOG_PATH)
    request = yaml.safe_load(REQUEST_PATH.read_text(encoding="utf-8"))
    del request["access"]["allowed_access_states"]

    with pytest.raises(SourceCatalogError, match="allowed_access_states"):
        resolve_source_plan(catalog, request)


def test_invalid_catalog_fails_before_routing():
    catalog = load_source_catalog(CATALOG_PATH)
    invalid = copy.deepcopy(catalog)
    del invalid["sources"][0]["routing_tier"]

    with pytest.raises(SourceCatalogError, match="routing_tier"):
        validate_source_catalog(invalid)


def test_reader_source_pool_prevents_silent_catalog_expansion():
    catalog = load_source_catalog(CATALOG_PATH)
    request = yaml.safe_load(REQUEST_PATH.read_text(encoding="utf-8"))
    request["access"]["candidate_source_ids"].remove("media-bloomberg")

    plan = resolve_source_plan(catalog, request)

    assert "media-bloomberg" not in {source["source_id"] for source in plan["selected_sources"]}
    assert {"source_id": "media-bloomberg", "reason": "outside_reader_source_pool"} in plan[
        "excluded_sources"
    ]


def test_catalog_rejects_mismatched_x_identity():
    catalog = load_source_catalog(CATALOG_PATH)
    invalid = copy.deepcopy(catalog)
    x_channel = next(
        channel for channel in invalid["sources"][0]["channels"] if channel["type"] == "x"
    )
    x_channel["handle"] = "@WrongHandle"

    with pytest.raises(SourceCatalogError, match="does not match handle"):
        validate_source_catalog(invalid)


def test_active_channel_requires_verified_status():
    catalog = load_source_catalog(CATALOG_PATH)
    broken = copy.deepcopy(catalog)
    broken["sources"][0]["channels"][0]["status"] = "unchecked_active"
    with pytest.raises(SourceCatalogError, match="active channel status must be verified"):
        validate_source_catalog(broken)


def test_source_plan_cli_writes_auditable_plan(tmp_path, capsys):
    out = tmp_path / "source-plan.json"

    assert main(
        [
            "source-plan",
            "--catalog",
            str(CATALOG_PATH),
            "--request",
            str(REQUEST_PATH),
            "--out",
            str(out),
        ]
    ) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["catalog_id"] == "investment-os-public-source-catalog"
    assert payload["catalog_sha256"].startswith("sha256:")
    assert payload["request_sha256"].startswith("sha256:")
    assert payload["selected_sources"]
    assert "source_plan=pass" in capsys.readouterr().out
