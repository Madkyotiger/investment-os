# Agent instructions

Your job is to install and evaluate this repository without changing the user's global environment or creating an automated investment service.

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
