from __future__ import annotations

import json
import os
import random
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from . import __version__

TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
DEFAULT_USER_AGENT = f"InvestmentOS/{__version__} (+https://github.com/Madkyotiger/investment-os)"


@dataclass
class HttpRequestError(RuntimeError):
    code: str
    message: str
    source_url: str
    transient: bool = False
    status_code: int | None = None

    def __str__(self) -> str:
        status = f" status={self.status_code}" if self.status_code is not None else ""
        return f"{self.code}{status}: {self.message}"

    def to_dict(self) -> dict[str, str | bool | int | None]:
        return {
            "code": self.code,
            "message": self.message,
            "source_url": self.source_url,
            "transient": self.transient,
            "status_code": self.status_code,
        }


class HttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        max_attempts: int = 3,
        max_response_bytes: int = 5_000_000,
        base_backoff_seconds: float = 0.25,
        opener: Callable | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.timeout_seconds = max(0.1, min(float(timeout_seconds), 30.0))
        self.max_attempts = max(1, min(int(max_attempts), 5))
        self.max_response_bytes = max(1, int(max_response_bytes))
        self.base_backoff_seconds = max(0.0, float(base_backoff_seconds))
        self.opener = opener or (lambda request, timeout: urllib.request.urlopen(request, timeout=timeout))
        self.sleeper = sleeper
        self.jitter = jitter

    def _headers(self, url: str, user_agent: str | None) -> dict[str, str]:
        if user_agent:
            return {"User-Agent": user_agent}
        if "sec.gov" in url:
            identity = os.getenv("SEC_EDGAR_IDENTITY", "").strip()
            if not identity:
                raise HttpRequestError(
                    "missing_identity",
                    "SEC_EDGAR_IDENTITY is required for SEC requests",
                    url,
                    transient=False,
                )
            return {"User-Agent": identity}
        return {"User-Agent": DEFAULT_USER_AGENT}

    def _request(self, url: str, expected_content_types: tuple[str, ...], user_agent: str | None) -> bytes:
        request = urllib.request.Request(url, headers=self._headers(url, user_agent))
        last_error: HttpRequestError | None = None
        for attempt in range(self.max_attempts):
            try:
                with self.opener(request, self.timeout_seconds) as response:
                    content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
                    if expected_content_types and not any(
                        content_type == expected or content_type.endswith(f"+{expected.split('/')[-1]}")
                        for expected in expected_content_types
                    ):
                        raise HttpRequestError(
                            "invalid_content_type",
                            f"expected {expected_content_types}, received {content_type or 'missing'}",
                            url,
                        )
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > self.max_response_bytes:
                        raise HttpRequestError("response_too_large", "response exceeded configured size limit", url)
                    body = response.read(self.max_response_bytes + 1)
                    if len(body) > self.max_response_bytes:
                        raise HttpRequestError("response_too_large", "response exceeded configured size limit", url)
                    return body
            except urllib.error.HTTPError as exc:
                transient = exc.code in TRANSIENT_STATUS_CODES
                last_error = HttpRequestError(
                    "http_status",
                    "upstream returned an unsuccessful status",
                    url,
                    transient=transient,
                    status_code=exc.code,
                )
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as exc:
                last_error = HttpRequestError("network_error", type(exc).__name__, url, transient=True)
            except HttpRequestError:
                raise
            if last_error and last_error.transient and attempt + 1 < self.max_attempts:
                delay = self.base_backoff_seconds * (2**attempt) + self.jitter() * 0.1
                self.sleeper(delay)
                continue
            if last_error:
                raise last_error
        raise last_error or HttpRequestError("network_error", "request failed", url)

    def get_json(self, url: str, *, user_agent: str | None = None) -> dict | list:
        body = self._request(url, ("application/json", "text/json"), user_agent)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpRequestError("malformed_json", "response was not valid JSON", url) from exc

    def get_text(
        self,
        url: str,
        *,
        user_agent: str | None = None,
        expected_content_types: tuple[str, ...] = ("text/plain", "text/csv", "application/csv", "text/html"),
    ) -> str:
        body = self._request(url, expected_content_types, user_agent)
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HttpRequestError("invalid_encoding", "response was not UTF-8", url) from exc
