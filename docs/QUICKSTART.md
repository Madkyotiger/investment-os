# Daily Brief Quickstart

This quickstart exercises the evidence-first daily path entirely offline. It uses synthetic sources, writes only local artifacts, and cannot send messages or create a schedule.

## Install and verify

```bash
uv sync --extra dev
uv run investment-os doctor
uv run investment-os demo --out .local/demo-output
```

## Run the daily workflow

```bash
rm -rf .local/daily-evaluation
uv run investment-os daily \
  --config configs/daily_brief.sample.yaml \
  --out .local/daily-evaluation
```

Expected result:

```text
daily_run=pass
delivery_mode=dry-run
```

The output directory contains:

- `brief.md`: maximum five evidence-gated reader items;
- `source_receipt.json`: source URL, source date, retrieval time, evidence state, freshness, and content hash;
- `manifest.json`: input fingerprint, item counts, source failure count, and artifact hashes;
- `run_state.json`: input change state and meaningful topic-change count;
- `topic_state.json`: durable thesis/evidence state;
- `source_errors.json`: structured source failures, including an empty list when none occurred;
- `delivery_preview.json`: proof that delivery stayed dry-run;
- `cache/source-records/`: stable cache records keyed by source.

## Verify idempotency

```bash
shasum -a 256 .local/daily-evaluation/brief.md
uv run investment-os daily \
  --config configs/daily_brief.sample.yaml \
  --out .local/daily-evaluation
shasum -a 256 .local/daily-evaluation/brief.md
python - <<'PY'
import json
from pathlib import Path

state = json.loads(Path('.local/daily-evaluation/run_state.json').read_text())
assert state['input_status'] == 'unchanged'
assert state['meaningful_changes'] == 0
print('idempotency=pass')
PY
```

The two brief hashes must match. Cache record count must not grow on the second identical run.

## Verify strict failure

The sample deliberately includes source-target-only and stale metadata rows. Strict mode must reject them:

```bash
uv run investment-os daily \
  --config configs/daily_brief.sample.yaml \
  --out .local/daily-strict \
  --strict
```

Expected: exit code `2` with `strict evidence gate failed`. This is fail-closed behavior, not an installation error.

## Operating boundaries

- `delivery_mode` must remain `dry-run`; any other value is rejected.
- No scheduler is installed by this repository.
- Do not put holdings, credentials, access tokens, or private profiles in tracked config.
- A source target or filing metadata row is not promotable evidence.
- Stale, mixed, unavailable, and incomplete body-read evidence stays out of the reader brief.
- The output is research context only. It does not recommend or execute trades.

## Current gaps

- Live official-source reliability varies and is not proven by the offline fixture.
- China official-source coverage is incomplete; AKShare and Tushare remain convenience/secondary adapters.
- Official Federal Reserve and U.S. Treasury endpoints remain source-check targets until stable retrieval paths are verified.
- Automated delivery and scheduling remain intentionally disabled pending human evaluation.