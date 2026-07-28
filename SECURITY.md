# Security and data handling

Do not commit API keys, access tokens, cookies, private keys, holdings, personal profiles, private research, raw browser captures, or delivery-channel identifiers.

Use environment variables for credentials and `*.local.*` or `*.private.*` for local configuration. Those patterns are ignored by Git.

The Feishu endpoint is read only from `INVESTMENT_OS_FEISHU_WEBHOOK_URL`; never pass it as a CLI argument or place it in YAML. Dry-run delivery does not read or require the endpoint and local previews never include it. Transport exceptions are replaced with bounded generic errors so the endpoint is not retained in error text.

Live Feishu delivery requires both `--confirm-send` and `INVESTMENT_OS_ENABLE_LIVE_DELIVERY=true`. Either gate missing means no network request. Quiet/empty completed briefs also make no request. Keep the enable variable unset during local evaluation, CI, and tests.

Delivery accepts only a brief registered by hash in a completed daily-run manifest. It does not update topic state or source caches. Payloads over the configured byte limit fail before transport, retries are bounded, and successful live sends are recorded by a content-derived dedup key.

Run this before every push:

```bash
uv run python scripts/public_release_guard.py
```

The guard is a release brake, not a complete secret scanner. Review the staged diff and Git history before publication. If you find a credential in history, revoke it first; deleting the current file is not enough.

Report security problems through GitHub's private vulnerability reporting when available. Do not place sensitive evidence in a public issue.
