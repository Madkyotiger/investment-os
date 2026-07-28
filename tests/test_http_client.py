from __future__ import annotations

import json
import urllib.error

import pytest

from investment_os.http_client import HttpClient, HttpRequestError


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json", status: int = 200):
        self.body = body
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


def test_http_client_retries_429_and_recovers():
    calls = []
    responses = [
        urllib.error.HTTPError("https://example.test", 429, "slow down", {}, None),
        FakeResponse(b'{"ok": true}'),
    ]

    def opener(request, timeout):
        calls.append((request, timeout))
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    client = HttpClient(opener=opener, sleeper=lambda _delay: None, jitter=lambda: 0.0, max_attempts=2)
    assert client.get_json("https://example.test") == {"ok": True}
    assert len(calls) == 2
    assert calls[0][1] <= 30


def test_http_client_retries_timeout_but_not_non_transient_status():
    attempts = 0

    def timeout_opener(_request, _timeout):
        nonlocal attempts
        attempts += 1
        raise TimeoutError("timed out")

    client = HttpClient(opener=timeout_opener, sleeper=lambda _delay: None, max_attempts=2)
    with pytest.raises(HttpRequestError) as error:
        client.get_json("https://example.test")
    assert error.value.code == "network_error"
    assert attempts == 2

    attempts = 0

    def not_found(_request, _timeout):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError("https://example.test", 404, "missing", {}, None)

    client = HttpClient(opener=not_found, sleeper=lambda _delay: None, max_attempts=3)
    with pytest.raises(HttpRequestError) as error:
        client.get_json("https://example.test")
    assert error.value.status_code == 404
    assert attempts == 1


def test_http_client_rejects_wrong_content_type_malformed_json_and_oversize():
    cases = [
        (FakeResponse(b"<html>no</html>", "text/html"), "invalid_content_type"),
        (FakeResponse(b"not json", "application/json"), "malformed_json"),
        (FakeResponse(b'{"large":"payload"}', "application/json"), "response_too_large"),
    ]
    for response, code in cases:
        client = HttpClient(opener=lambda _request, _timeout, value=response: value, max_response_bytes=8)
        with pytest.raises(HttpRequestError) as error:
            client.get_json("https://example.test")
        assert error.value.code == code
        assert "payload" not in str(error.value)


def test_http_client_uses_sec_identity_without_exposing_it(monkeypatch):
    captured = {}
    monkeypatch.setenv("SEC_EDGAR_IDENTITY", "researcher@example.test")

    def opener(request, _timeout):
        captured.update(dict(request.header_items()))
        return FakeResponse(json.dumps({"ok": True}).encode())

    HttpClient(opener=opener).get_json("https://data.sec.gov/submissions/example.json")
    assert captured["User-agent"] == "researcher@example.test"
