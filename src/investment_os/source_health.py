from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Mapping


class SourceHealthStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.path.exists() or not self.path.read_text(encoding="utf-8").strip():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get(self, source_name: str) -> dict[str, object]:
        return dict(self._load().get(source_name, {}))

    def all(self) -> dict[str, dict[str, object]]:
        return {name: dict(record) for name, record in self._load().items()}

    def record_success(
        self,
        source_name: str,
        source_url: str,
        occurred_at: datetime,
        *,
        content_hash: str = "",
        as_of_date: str = "",
        freshness_status: str = "",
        freshness_threshold_days: int = 0,
        evidence_status: str = "",
    ) -> None:
        data = self._load()
        record = data.setdefault(source_name, {})
        observation = {
            "source_url": source_url,
            "retrieved_at": occurred_at.isoformat(),
            "content_hash": content_hash,
            "as_of_date": as_of_date,
            "freshness_status": freshness_status,
            "freshness_threshold_days": freshness_threshold_days,
            "evidence_status": evidence_status,
        }
        record.update(
            {
                "last_success_at": occurred_at.isoformat(),
                "last_observation_at": occurred_at.isoformat(),
                "last_observation_status": "success",
                "last_observation": observation,
            }
        )
        previous = record.get("last_known_good")
        previous_as_of = str(previous.get("as_of_date", "")) if isinstance(previous, dict) else ""
        if not previous_as_of or as_of_date >= previous_as_of:
            record["last_known_good"] = observation
        self._write(data)

    def record_observation(
        self,
        source_name: str,
        source_url: str,
        occurred_at: datetime,
        *,
        content_hash: str = "",
        as_of_date: str = "",
        freshness_status: str = "",
        freshness_threshold_days: int = 0,
        evidence_status: str = "",
    ) -> None:
        data = self._load()
        record = data.setdefault(source_name, {})
        record.update(
            {
                "last_observation_at": occurred_at.isoformat(),
                "last_observation_status": freshness_status or evidence_status or "observed",
                "last_observation": {
                    "source_url": source_url,
                    "retrieved_at": occurred_at.isoformat(),
                    "content_hash": content_hash,
                    "as_of_date": as_of_date,
                    "freshness_status": freshness_status,
                    "freshness_threshold_days": freshness_threshold_days,
                    "evidence_status": evidence_status,
                },
            }
        )
        self._write(data)

    def record_failure(
        self,
        source_name: str,
        error: Mapping[str, object],
        occurred_at: datetime,
    ) -> None:
        data = self._load()
        record = data.setdefault(source_name, {})
        safe_error = {
            "code": str(error.get("code", "source_error")),
            "message": str(error.get("message", "source request failed")),
            "source_url": str(error.get("source_url", "")),
            "transient": bool(error.get("transient", False)),
            "status_code": error.get("status_code"),
        }
        record.update(
            {
                "last_failure_at": occurred_at.isoformat(),
                "last_error": safe_error,
                "last_observation_at": occurred_at.isoformat(),
                "last_observation_status": "failure",
            }
        )
        self._write(data)
