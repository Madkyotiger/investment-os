from __future__ import annotations

import json
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from io import BytesIO
from pathlib import Path

import pytest

from investment_os.delivery import DeliveryError
from investment_os.feishu_delivery import MAX_PAYLOAD_BYTES, deliver_feishu, feishu_dedup_key


LIVE_ENV = {
    "INVESTMENT_OS_ENABLE_LIVE_DELIVERY": "true",
    "INVESTMENT_OS_FEISHU_WEBHOOK_URL": "https://secret.invalid/webhook/token-value",
}


def test_payload_size_guard_counts_serialized_utf8_bytes(tmp_path: Path):
    with pytest.raises(DeliveryError, match="payload exceeds"):
        deliver_feishu(
            "中" * MAX_PAYLOAD_BYTES,
            brief_path=tmp_path / "brief.md",
            dry_run=True,
            env={},
        )


def test_retry_is_bounded_and_dedup_prevents_second_live_send(tmp_path: Path):
    calls: list[int] = []

    def flaky_post(_url, _body, _headers, _timeout):
        calls.append(1)
        if len(calls) < 3:
            return 503, b'{"code": 1}'
        return 200, b'{"code": 0, "msg": "success"}'

    first = deliver_feishu(
        "material change",
        brief_path=tmp_path / "brief.md",
        dry_run=False,
        confirm_send=True,
        env=LIVE_ENV,
        post=flaky_post,
        sleep=lambda _seconds: None,
    )
    second = deliver_feishu(
        "material change",
        brief_path=tmp_path / "brief.md",
        dry_run=False,
        confirm_send=True,
        env=LIVE_ENV,
        post=lambda *_args: pytest.fail("deduplicated send must not call transport"),
    )

    assert first.status == "sent"
    assert first.attempts == 3
    assert second.status == "deduplicated"
    assert len(calls) == 3
    assert first.dedup_key == second.dedup_key == feishu_dedup_key("material change")


def test_transport_failure_does_not_leak_webhook(tmp_path: Path):
    secret = LIVE_ENV["INVESTMENT_OS_FEISHU_WEBHOOK_URL"]

    def failing_post(url, _body, _headers, _timeout):
        raise RuntimeError(f"cannot reach {url}")

    with pytest.raises(DeliveryError) as captured:
        deliver_feishu(
            "material change",
            brief_path=tmp_path / "brief.md",
            dry_run=False,
            confirm_send=True,
            env=LIVE_ENV,
            post=failing_post,
            sleep=lambda _seconds: None,
        )

    assert secret not in str(captured.value)


@pytest.mark.parametrize(("status", "expected_calls"), [(400, 1), (503, 3)])
def test_default_post_translates_http_error_for_status_aware_retry(
    monkeypatch, tmp_path: Path, status: int, expected_calls: int
):
    calls: list[int] = []

    def http_error(_request, timeout):
        assert timeout == 10.0
        calls.append(1)
        raise urllib.error.HTTPError(
            LIVE_ENV["INVESTMENT_OS_FEISHU_WEBHOOK_URL"],
            status,
            "upstream failure",
            Message(),
            BytesIO(b'{"code": 19001, "msg": "rejected"}'),
        )

    monkeypatch.setattr("investment_os.feishu_delivery.urllib.request.urlopen", http_error)
    with pytest.raises(DeliveryError, match=f"HTTP status {status}") as captured:
        deliver_feishu(
            "material change",
            brief_path=tmp_path / "brief.md",
            dry_run=False,
            confirm_send=True,
            env=LIVE_ENV,
            sleep=lambda _seconds: None,
        )

    assert len(calls) == expected_calls
    assert LIVE_ENV["INVESTMENT_OS_FEISHU_WEBHOOK_URL"] not in str(captured.value)


def test_preview_contains_payload_and_dedup_but_no_secret(tmp_path: Path):
    preview_path = tmp_path / "preview.json"

    result = deliver_feishu(
        "material change",
        brief_path=tmp_path / "brief.md",
        dry_run=True,
        env=LIVE_ENV,
        preview_path=preview_path,
    )
    preview_text = preview_path.read_text(encoding="utf-8")
    preview = json.loads(preview_text)

    assert result.status == "dry_run"
    assert preview["dedup_key"] == feishu_dedup_key("material change")
    assert preview["payload"]["content"]["text"] == "material change"
    assert LIVE_ENV["INVESTMENT_OS_FEISHU_WEBHOOK_URL"] not in preview_text


def test_http_2xx_application_error_never_records_dedup(tmp_path: Path):
    brief_path = tmp_path / "brief.md"

    with pytest.raises(DeliveryError, match="application code"):
        deliver_feishu(
            "material change",
            brief_path=brief_path,
            dry_run=False,
            confirm_send=True,
            env=LIVE_ENV,
            post=lambda *_args: (200, b'{"code": 19001, "msg": "rejected"}'),
        )

    dedup_path = tmp_path / ".delivery" / "feishu_sent.json"
    assert not dedup_path.exists()
    retry = deliver_feishu(
        "material change",
        brief_path=brief_path,
        dry_run=False,
        confirm_send=True,
        env=LIVE_ENV,
        post=lambda *_args: (200, b'{"code": 0, "msg": "success"}'),
    )
    assert retry.status == "sent"


def test_concurrent_live_delivery_claim_allows_only_one_post(tmp_path: Path):
    brief_path = tmp_path / "brief.md"
    first_entered = threading.Event()
    release_first = threading.Event()
    calls: list[int] = []

    def blocking_post(_url, _body, _headers, _timeout):
        calls.append(1)
        first_entered.set()
        assert release_first.wait(timeout=2)
        return 200, b'{"code": 0, "msg": "success"}'

    kwargs = {
        "brief_path": brief_path,
        "dry_run": False,
        "confirm_send": True,
        "env": LIVE_ENV,
        "post": blocking_post,
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(deliver_feishu, "material change", **kwargs)
        assert first_entered.wait(timeout=2)
        second = executor.submit(deliver_feishu, "material change", **kwargs)
        release_first.set()
        results = [first.result(timeout=2), second.result(timeout=2)]

    assert sorted(result.status for result in results) == ["deduplicated", "sent"]
    assert calls == [1]