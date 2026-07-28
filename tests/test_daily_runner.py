from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from investment_os.daily_runner import DailyRunError, run_daily


CONFIG = Path("configs/daily_brief.sample.yaml")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_offline_daily_run_writes_auditable_artifacts_and_is_idempotent(tmp_path: Path):
    first = run_daily(CONFIG, tmp_path)
    first_hash = _sha256(first.brief_path)
    first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))

    second = run_daily(CONFIG, tmp_path)
    second_hash = _sha256(second.brief_path)
    second_state = json.loads(second.run_state_path.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))

    assert first_hash == second_hash
    assert second_state["input_status"] == "unchanged"
    assert second_state["meaningful_changes"] == 0
    assert first_manifest["delivery_mode"] == "dry-run"
    assert first_manifest["promoted_items"] == 2
    assert first_manifest["blocked_items"] == 2
    for name, metadata in second_manifest["artifacts"].items():
        path = tmp_path / name
        assert path.exists()
        assert _sha256(path) == metadata["sha256"]
    assert len(list((tmp_path / "cache" / "source-records").glob("*.json"))) == 4


def test_daily_run_excludes_targets_metadata_and_stale_items(tmp_path: Path):
    result = run_daily(CONFIG, tmp_path)
    brief = result.brief_path.read_text(encoding="utf-8")
    receipt = json.loads(result.source_receipt_path.read_text(encoding="utf-8"))

    assert "ACME 发布季度一手文件" in brief
    assert "示例市场广度出现变化" in brief
    assert "美联储官方资料目标" not in brief
    assert "过期元数据" not in brief
    assert all(row["source_url"] and row["evidence_status"] for row in receipt)


def test_strict_mode_fails_on_blocked_or_incomplete_evidence(tmp_path: Path):
    with pytest.raises(DailyRunError, match="strict evidence gate"):
        run_daily(CONFIG, tmp_path, strict=True)


def test_manifest_reports_structured_source_failures(tmp_path: Path):
    raw = json.loads(Path("tests/fixtures/daily_brief_sources.json").read_text(encoding="utf-8"))
    raw["source_errors"] = [
        {
            "code": "timeout",
            "source": "synthetic-official-source",
            "retryable": True,
            "message": "request timed out",
        }
    ]
    fixture = tmp_path / "failure-fixture.json"
    fixture.write_text(json.dumps(raw), encoding="utf-8")
    config = tmp_path / "daily.yaml"
    config.write_text(
        "\n".join(
            [
                f"profile_config: {Path('configs/profiles.sample.yaml').resolve()}",
                "profile_id: founder_operator",
                f"input_fixture: {fixture}",
                "delivery_mode: dry-run",
            ]
        ),
        encoding="utf-8",
    )

    result = run_daily(config, tmp_path / "out")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    failures = json.loads(result.source_errors_path.read_text(encoding="utf-8"))

    assert manifest["source_failure_count"] == 1
    assert failures[0]["code"] == "timeout"
