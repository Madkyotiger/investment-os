# Agent instructions

Your job is to install and evaluate this repository without changing the user's global environment or creating an automated investment service.

## Market-scope contract

Investment OS is a multi-market research system. Preserve the U.S./Hong Kong `daily` watchlist path, market and macro proxies, and optional global research sources when adding or changing a market-specific adapter. `a-share-daily` is additive and stock-specific; do not make it the default for other markets, route Hong Kong or U.S. symbols through it, or remove other source families merely because an A-share task is active.

## Required path

1. Confirm Python is 3.11 or 3.12 and `uv` is available.
2. Run `uv sync --frozen --extra dev` inside the checkout.
3. Run `uv run investment-os doctor`.
4. Run `uv run investment-os demo --out demo-output`.
5. Run `uv run pytest -q`.
6. Read the generated brief and report. Confirm they contain research questions and evidence limits, not trade instructions.
7. Return the exact commands, pass/fail state, and output paths.

## Live-source test

Live access is optional. Use the isolated `market` profile only when the user asks for a current-source check:

```bash
cp configs/watchlist.sample.yaml configs/watchlist.local.yaml
uv run --frozen --isolated --link-mode copy --extra market \
  investment-os run --config configs/watchlist.local.yaml --out live-output --strict
```

For an A-share request, use the separate keyless China profile and stock-specific command:

```bash
uv run --frozen --isolated --link-mode copy --extra china \
  investment-os doctor --probe china-keyless
uv run --frozen --isolated --link-mode copy --extra china \
  investment-os a-share-daily \
  --config configs/a-share-watchlist.sample.yaml \
  --out .local/a-share-agent-test \
  --strict
```

Use `scripts/verify_dependency_profiles.py` when the task is to verify optional package availability without calling providers or adding those packages to `.venv`:

```bash
uv run --no-project python scripts/verify_dependency_profiles.py market
uv run --no-project python scripts/verify_dependency_profiles.py global-research china
```

Do not add credentials to files. Do not print credential values. Do not enable cron, notifications, brokerage access, or order execution during evaluation.

## Acceptance

Evaluation passes only when:

- doctor exits `0`;
- offline demo exits `0` and writes all five artifacts;
- tests pass;
- `scripts/public_release_guard.py` passes;
- any live run reports at least one `data_quality=ok` row when `--strict` is used.

A report file with zero usable source rows is a failed live test, not a successful run.

## Reader output contract

The acceptance record above is the engineering receipt, not the default user answer.

- When the user asks for an A-share observation or daily brief, run `investment-os a-share-daily` and return the contents of `brief.md` first.
- Keep commands, test counts, adapter names, status codes, logs, and paths out of the reader brief. Add at most one compact pass/fail receipt after it.
- Detailed evidence belongs in `evidence-ledger.csv`, `coverage-matrix.md`, and `source-receipt.json`; show it only when the user asks to audit or troubleshoot.
- `no_event` is a successful source check with no matching event. `source_error` is a failed source read. Never collapse one into the other.
- Tushare is an optional second source for the keyless A-share path. Missing `TUSHARE_TOKEN` does not make `a-share-daily` degraded.
- Turnover, generic fund-flow fields, and margin financing are not verified institutional net flow. Do not rename them to imply otherwise.
