# Daily Brief Quickstart

This route exercises the exact daily and delivery contracts entirely offline. It uses synthetic sources, writes only local artifacts, and cannot create a schedule.

## Install and verify

```bash
uv sync --extra dev
uv run investment-os doctor
uv run investment-os demo --out .local/demo-output
```

## Run the deterministic daily workflow

```bash
rm -rf .local/daily-run-1 .local/daily-run-2 .local/daily-state.json
uv run investment-os daily \
  --config configs/watchlist.sample.yaml \
  --profile configs/profiles.sample.yaml \
  --state .local/daily-state.json \
  --out .local/daily-run-1 \
  --strict \
  --offline
```

Expected result: exit `0` and `daily_run=completed`. Offline mode is deterministic. `--strict` does not reject blocked synthetic candidates because strict all-sources-failed behavior applies to live collection.

The completed output contains:

- `cxo_daily_brief.md`: maximum five changed, evidence-gated reader items;
- `source_receipt.json`: source URL, source/retrieval dates, evidence/freshness state, content hash, and promotion decision;
- `manifest.json`: completed/quiet result, source successes/failures, item counts, paths, and artifact hashes;
- `run_state.json`: run result, input fingerprint, meaningful-change count, and promoted IDs;
- `topic_changes.json` and `topic_changes.csv`: state comparison used by promotion;
- `source_errors.json`: structured collection failures, including an empty list when none occurred;
- `source_health.json`: current diagnostics plus explicitly labeled current/stale last-known-good state;
- `delivery_preview.json`: explicit proof that the daily command did not request delivery;
- `cache/source-records/`: local source receipts.

The durable topic state exists at the exact `--state` path. Live runs also maintain sibling `*.macro.json` and `*.source-health.json` files for revision detection and source health. They are staged with the run and committed only against a complete matching manifest; last-known-good data is diagnostic and is never substituted or promoted as a current observation.

## Verify idempotency and quiet state

```bash
uv run investment-os daily \
  --config configs/watchlist.sample.yaml \
  --profile configs/profiles.sample.yaml \
  --state .local/daily-state.json \
  --out .local/daily-run-2 \
  --strict \
  --offline
```

Expected: exit `0`, `daily_run=quiet`, zero promoted IDs, and quiet wording in the second brief. Unchanged evidence is not re-promoted.

## Live collection and strict semantics

Omit `--offline` to use the existing public SEC, FRED, yfinance, and Stooq collectors:

```bash
uv run investment-os daily \
  --config configs/watchlist.sample.yaml \
  --profile configs/profiles.sample.yaml \
  --state .local/live-state.json \
  --out .local/live-run \
  --strict
```

Live collection fails closed and never substitutes synthetic observations. In strict mode, exit `2` means every fresh usable live source failed; a successfully fetched observation outside its configured cadence/staleness window is not usable. `configs/macro_series.yaml` defines each FRED series threshold and a five-calendar-day market snapshot threshold so weekends/holidays can remain current without accepting arbitrarily old closes. This config is bundled as package data and used automatically when the checkout-relative file is unavailable. A blocked source target, metadata-only filing, or one failed source does not fail strict mode when another fresh usable live source succeeded. A successful collection may still return `quiet` when no changed promotable item exists.

SEC requests should use `SEC_EDGAR_IDENTITY` in the environment. Do not put it in tracked files.

## Preview completed Feishu payload

```bash
uv run investment-os deliver \
  --brief .local/daily-run-1/cxo_daily_brief.md \
  --channel feishu \
  --dry-run
```

Expected: exit `0`, `delivery=dry_run`, `sent=false`, and a local `feishu_delivery_preview.json`. Dry-run requires no endpoint and performs no POST. Delivery rejects drafts, incomplete runs, and briefs changed after the manifest was written. Quiet/empty completed briefs return `delivery=quiet` and do not send.

Live sending remains a separately authorized operation. The code requires `--confirm-send`, `INVESTMENT_OS_ENABLE_LIVE_DELIVERY=true`, and `INVESTMENT_OS_FEISHU_WEBHOOK_URL` from the environment. HTTP 2xx alone is not success; the response body must also contain Feishu application code `0`, otherwise no dedup receipt is recorded. Do not set those gates during evaluation.

An exclusive local file claim serializes dedup lookup, POST, and receipt write for processes using the same brief directory. This closes the ordinary concurrent read/POST/write race but is only best-effort: a crash after Feishu accepts a POST and before the local receipt write can still cause a duplicate on retry. The transport therefore does not claim exactly-once delivery.

## Current gaps

- Live official-source reliability varies and is not proven by the synthetic fixture.
- China official-source coverage is incomplete; AKShare and Tushare remain convenience/secondary adapters.
- Official Federal Reserve and U.S. Treasury endpoints remain source-check targets where stable retrieval is unresolved.
- No scheduler is implemented or enabled.
- Live Feishu delivery has unit coverage with injected transports but has not been exercised against a real endpoint.