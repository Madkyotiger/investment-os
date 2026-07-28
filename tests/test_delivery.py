from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from investment_os.delivery import DeliveryError, deliver_brief


def _completed_brief(tmp_path: Path, text: str = "# Brief\n\nMaterial change.\n", result: str = "completed") -> Path:
    brief = tmp_path / "cxo_daily_brief.md"
    brief.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(brief.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "run_complete": True,
                "result": result,
                "artifacts": {brief.name: {"sha256": digest, "bytes": len(brief.read_bytes())}},
            }
        ),
        encoding="utf-8",
    )
    return brief


def test_delivery_requires_a_completed_unmodified_brief(tmp_path: Path):
    brief = tmp_path / "cxo_daily_brief.md"
    brief.write_text("draft", encoding="utf-8")

    with pytest.raises(DeliveryError, match="completed daily manifest"):
        deliver_brief(brief, channel="feishu")

    completed = _completed_brief(tmp_path)
    completed.write_text("tampered", encoding="utf-8")
    with pytest.raises(DeliveryError, match="artifact hash"):
        deliver_brief(completed, channel="feishu")


def test_delivery_defaults_to_local_dry_run_without_webhook(tmp_path: Path):
    brief = _completed_brief(tmp_path)

    result = deliver_brief(brief, channel="feishu", env={})
    preview = json.loads(result.preview_path.read_text(encoding="utf-8"))

    assert result.status == "dry_run"
    assert result.sent is False
    assert preview["channel"] == "feishu"
    assert preview["payload"]["content"]["text"].startswith("# Brief")
    assert "webhook" not in json.dumps(preview).lower()


def test_quiet_or_empty_completed_brief_never_calls_transport(tmp_path: Path):
    brief = _completed_brief(tmp_path, text="", result="quiet")
    calls = []

    result = deliver_brief(
        brief,
        channel="feishu",
        dry_run=False,
        confirm_send=True,
        env={
            "INVESTMENT_OS_ENABLE_LIVE_DELIVERY": "true",
            "INVESTMENT_OS_FEISHU_WEBHOOK_URL": "https://secret.invalid/hook",
        },
        post=lambda *_args, **_kwargs: calls.append(True),
    )

    assert result.status == "quiet"
    assert result.sent is False
    assert calls == []


@pytest.mark.parametrize(
    "confirm_send,env",
    [
        (False, {"INVESTMENT_OS_ENABLE_LIVE_DELIVERY": "true", "INVESTMENT_OS_FEISHU_WEBHOOK_URL": "secret"}),
        (True, {"INVESTMENT_OS_FEISHU_WEBHOOK_URL": "secret"}),
    ],
)
def test_live_send_requires_both_confirmation_gates(tmp_path: Path, confirm_send: bool, env: dict[str, str]):
    brief = _completed_brief(tmp_path)

    with pytest.raises(DeliveryError, match="live delivery is disabled"):
        deliver_brief(
            brief,
            channel="feishu",
            dry_run=False,
            confirm_send=confirm_send,
            env=env,
            post=lambda *_args, **_kwargs: pytest.fail("transport must not be called"),
        )


def test_cli_delivery_dry_run_uses_completed_brief(tmp_path: Path, capsys):
    from investment_os.cli import main

    brief = _completed_brief(tmp_path)

    assert main(["deliver", "--brief", str(brief), "--channel", "feishu", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "delivery=dry_run" in output
    assert "preview=" in output