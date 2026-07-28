from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path
from typing import BinaryIO, Callable, Iterator, Mapping

from .delivery import DeliveryError, DeliveryResult


FEISHU_WEBHOOK_ENV = "INVESTMENT_OS_FEISHU_WEBHOOK_URL"
LIVE_DELIVERY_ENV = "INVESTMENT_OS_ENABLE_LIVE_DELIVERY"
MAX_PAYLOAD_BYTES = 20_000
MAX_ATTEMPTS = 3
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_feishu_payload(text: str) -> tuple[dict[str, object], bytes]:
    payload: dict[str, object] = {"msg_type": "text", "content": {"text": text}}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise DeliveryError(f"Feishu payload exceeds {MAX_PAYLOAD_BYTES} UTF-8 bytes")
    return payload, encoded


def feishu_dedup_key(text: str) -> str:
    _, encoded = build_feishu_payload(text)
    return "sha256:" + hashlib.sha256(b"feishu\0" + encoded).hexdigest()


def _default_post(url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is an explicit env gate.
        return int(response.status), response.read()


def _enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _load_dedup(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeliveryError("local delivery dedup receipt is invalid") from error
    return {str(value) for value in raw.get("sent", [])} if isinstance(raw, dict) else set()


def _preview_path(brief_path: Path, preview_path: Path | None) -> Path:
    return preview_path or brief_path.parent / "feishu_delivery_preview.json"


@contextmanager
def _exclusive_claim(path: Path) -> Iterator[BinaryIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        flock(handle.fileno(), LOCK_EX)
        try:
            yield handle
        finally:
            flock(handle.fileno(), LOCK_UN)


def _application_code(body: bytes) -> int:
    try:
        payload = json.loads(body.decode("utf-8"))
        raw_code = payload.get("code", payload.get("StatusCode")) if isinstance(payload, dict) else None
        if raw_code is None:
            raise ValueError("missing application code")
        return int(str(raw_code))
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeliveryError("Feishu delivery returned an invalid application response") from error


def deliver_feishu(
    text: str,
    *,
    brief_path: Path,
    dry_run: bool = True,
    confirm_send: bool = False,
    env: Mapping[str, str] | None = None,
    preview_path: Path | None = None,
    post: Callable[[str, bytes, Mapping[str, str], float], tuple[int, bytes]] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> DeliveryResult:
    environment = os.environ if env is None else env
    preview = _preview_path(brief_path, preview_path)
    if not text.strip():
        _atomic_json(preview, {"channel": "feishu", "status": "quiet", "sent": False})
        return DeliveryResult("quiet", "feishu", preview, "", sent=False)

    payload, encoded = build_feishu_payload(text)
    dedup_key = feishu_dedup_key(text)
    preview_record = {
        "channel": "feishu",
        "status": "dry_run" if dry_run else "pending",
        "sent": False,
        "dedup_key": dedup_key,
        "payload_bytes": len(encoded),
        "payload": payload,
    }
    _atomic_json(preview, preview_record)
    if dry_run:
        return DeliveryResult("dry_run", "feishu", preview, dedup_key, sent=False)

    if not confirm_send or not _enabled(environment.get(LIVE_DELIVERY_ENV, "")):
        raise DeliveryError("live delivery is disabled; --confirm-send and the explicit environment enable are both required")
    endpoint = environment.get(FEISHU_WEBHOOK_ENV, "").strip()
    if not endpoint:
        raise DeliveryError(f"live delivery is disabled; {FEISHU_WEBHOOK_ENV} is not configured")

    delivery_dir = brief_path.parent / ".delivery"
    dedup_path = delivery_dir / "feishu_sent.json"
    claim_path = delivery_dir / "feishu.lock"
    transport = post or _default_post
    wait = sleep or time.sleep
    with _exclusive_claim(claim_path):
        sent_keys = _load_dedup(dedup_path)
        if dedup_key in sent_keys:
            preview_record["status"] = "deduplicated"
            _atomic_json(preview, preview_record)
            return DeliveryResult("deduplicated", "feishu", preview, dedup_key, sent=False)

        status = 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                status, response_body = transport(endpoint, encoded, {"Content-Type": "application/json"}, 10.0)
                status = int(status)
            except Exception:
                if attempt == MAX_ATTEMPTS:
                    # Do not retain transport exceptions: they can contain the secret endpoint.
                    raise DeliveryError(f"Feishu delivery failed after {MAX_ATTEMPTS} bounded attempts") from None
                wait(0.25 * (2 ** (attempt - 1)))
                continue
            if 200 <= status < 300:
                application_code = _application_code(response_body)
                if application_code != 0:
                    raise DeliveryError(f"Feishu delivery failed with application code {application_code}")
                sent_keys.add(dedup_key)
                _atomic_json(dedup_path, {"sent": sorted(sent_keys)})
                preview_record.update({"status": "sent", "sent": True, "attempts": attempt})
                _atomic_json(preview, preview_record)
                return DeliveryResult("sent", "feishu", preview, dedup_key, sent=True, attempts=attempt)
            if status not in TRANSIENT_STATUSES or attempt == MAX_ATTEMPTS:
                raise DeliveryError(f"Feishu delivery failed with HTTP status {status}")
            wait(0.25 * (2 ** (attempt - 1)))
    raise DeliveryError("Feishu delivery failed within the bounded retry policy")