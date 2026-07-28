from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_CACHE_DIR = Path(".cache/investment_os")


def cache_root() -> Path:
    configured = os.getenv("INVEST_ADVISOR_CACHE_DIR")
    return Path(configured) if configured else DEFAULT_CACHE_DIR


def cache_enabled() -> bool:
    return os.getenv("INVEST_ADVISOR_DISABLE_CACHE", "").lower() not in {"1", "true", "yes"}


def cache_key(*parts: object) -> str:
    raw = "::".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def cache_path(namespace: str, key: str, suffix: str) -> Path:
    safe_namespace = namespace.strip("/").replace("..", "_")
    safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return cache_root() / safe_namespace / f"{key}{safe_suffix}"


def read_text(namespace: str, key: str, suffix: str = ".txt") -> tuple[str | None, Path]:
    path = cache_path(namespace, key, suffix)
    if not cache_enabled() or not path.exists():
        return None, path
    return path.read_text(encoding="utf-8"), path


def write_text(namespace: str, key: str, content: str, suffix: str = ".txt") -> Path:
    path = cache_path(namespace, key, suffix)
    if not cache_enabled():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_json(namespace: str, key: str, suffix: str = ".json") -> tuple[Any | None, Path]:
    path = cache_path(namespace, key, suffix)
    if not cache_enabled() or not path.exists():
        return None, path
    return json.loads(path.read_text(encoding="utf-8")), path


def write_json(namespace: str, key: str, content: Any, suffix: str = ".json") -> Path:
    path = cache_path(namespace, key, suffix)
    if not cache_enabled():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_record(
    namespace: str,
    key: str,
    content: Any,
    *,
    source_url: str,
    retrieved_at: datetime | None = None,
) -> Path:
    path = cache_path(namespace, key, ".record.json")
    if not cache_enabled():
        return path
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    record = {
        "content": content,
        "source_url": source_url,
        "retrieved_at": retrieved_at.isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def read_record(
    namespace: str,
    key: str,
    *,
    now: datetime | None = None,
    max_age: timedelta,
    allow_stale: bool = False,
) -> tuple[dict[str, Any] | None, Path]:
    path = cache_path(namespace, key, ".record.json")
    if not cache_enabled() or not path.exists():
        return None, path
    raw = json.loads(path.read_text(encoding="utf-8"))
    retrieved_at = datetime.fromisoformat(str(raw["retrieved_at"]).replace("Z", "+00:00"))
    now = now or datetime.now(timezone.utc)
    stale = now - retrieved_at > max_age
    if stale and not allow_stale:
        return None, path
    return {
        "content": raw.get("content"),
        "source_url": str(raw.get("source_url", "")),
        "retrieved_at": retrieved_at.isoformat(),
        "freshness_status": "stale" if stale else "current",
    }, path


def write_record_at(
    root: Path,
    key: str,
    content: Any,
    *,
    source_url: str,
    retrieved_at: datetime,
) -> Path:
    path = root / f"{key}.record.json"
    record = {
        "content": content,
        "source_url": source_url,
        "retrieved_at": retrieved_at.isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
