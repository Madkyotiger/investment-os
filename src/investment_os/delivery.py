from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


class DeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    channel: str
    preview_path: Path
    dedup_key: str
    sent: bool = False
    attempts: int = 0


def _completed_brief(brief_path: Path) -> tuple[str, str]:
    if not brief_path.is_file():
        raise DeliveryError(f"brief file not found: {brief_path}")
    manifest_path = brief_path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise DeliveryError("delivery requires a completed daily manifest beside the brief")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeliveryError("delivery requires a valid completed daily manifest") from error
    result = str(manifest.get("result", ""))
    if manifest.get("run_complete") is not True or result not in {"completed", "quiet"}:
        raise DeliveryError("delivery requires a completed daily manifest")
    artifact = (manifest.get("artifacts") or {}).get(brief_path.name)
    if not isinstance(artifact, dict) or not artifact.get("sha256"):
        raise DeliveryError("completed daily manifest does not register the brief artifact")
    brief_bytes = brief_path.read_bytes()
    actual_hash = hashlib.sha256(brief_bytes).hexdigest()
    if actual_hash != str(artifact["sha256"]):
        raise DeliveryError("brief artifact hash does not match the completed daily manifest")
    return brief_bytes.decode("utf-8"), result


def deliver_brief(
    brief_path: Path,
    *,
    channel: str,
    dry_run: bool = True,
    confirm_send: bool = False,
    env: Mapping[str, str] | None = None,
    preview_path: Path | None = None,
    post: Callable[..., int] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> DeliveryResult:
    """Deliver only a hash-verified completed brief; never reads or updates research state."""
    brief_text, run_result = _completed_brief(brief_path)
    if channel != "feishu":
        raise DeliveryError(f"unsupported delivery channel: {channel}")
    from .feishu_delivery import deliver_feishu

    return deliver_feishu(
        "" if run_result == "quiet" else brief_text,
        brief_path=brief_path,
        dry_run=dry_run,
        confirm_send=confirm_send,
        env=os.environ if env is None else env,
        preview_path=preview_path,
        post=post,
        sleep=sleep,
    )