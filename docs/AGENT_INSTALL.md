# Agent installation and test

This route keeps the test reversible. It creates one checkout, one project-local environment, and one output directory.

## Repository checkout

```bash
git clone https://github.com/Madkyotiger/investment-os.git
cd investment-os
uv sync --frozen --extra dev
```

`uv` stores the environment under the project. Do not install packages into the system Python.

## Deterministic test

```bash
uv run investment-os doctor
uv run investment-os demo --out demo-output
uv run pytest -q
uv run python scripts/public_release_guard.py
```

Expected result:

- each command exits `0`;
- the demo reports `quality_scan=pass`;
- `demo-output` contains five files;
- the test count is non-zero and all tests pass.

The offline demo uses deterministic synthetic prices and synthetic source candidates. It checks the software path, not the current market.

Run the exact daily path with explicit, separate state:

```bash
uv run investment-os daily \
  --config configs/watchlist.sample.yaml \
  --profile configs/profiles.sample.yaml \
  --state .local/agent-state.json \
  --out .local/agent-run \
  --offline
```

The completed `manifest.json` and its artifact hashes are the handoff boundary. Channel selection and message delivery belong to the downstream runtime.

## Optional live market test

Use an isolated environment so optional market packages do not remain in the project `.venv`:

```bash
cp configs/watchlist.sample.yaml configs/watchlist.local.yaml
uv run --frozen --isolated --link-mode copy --extra market \
  investment-os run \
  --config configs/watchlist.local.yaml \
  --out live-output \
  --strict
```

Exit code `2` means the command produced no usable live rows. Check network access and provider behavior; do not reinterpret a degraded run as success.

## Keyless A-share test

Use the isolated China dependency profile. A Tushare token is not required:

```bash
uv run --frozen --isolated --link-mode copy --extra china \
  investment-os doctor --probe china-keyless
uv run --frozen --isolated --link-mode copy --extra china \
  investment-os a-share-daily \
  --config configs/a-share-watchlist.sample.yaml \
  --out .local/a-share-agent-test \
  --strict
```

Expected result: the probe reports `china_keyless_readiness=ready`, the run exits `0`, and the output contains `brief.md`, `evidence-ledger.csv`, `coverage-matrix.md`, and `source-receipt.json`. A successful `no_event` is not a source failure. Missing `TUSHARE_TOKEN` is `optional_source_not_configured`, not a degraded keyless run.

For a user asking for the result, paste `brief.md` first. Keep commands, tests, paths, adapter names, and source errors in a one-line receipt or the audit files unless the user explicitly asks to troubleshoot.

To check optional package profiles without calling providers:

```bash
uv run --no-project python scripts/verify_dependency_profiles.py market
uv run --no-project python scripts/verify_dependency_profiles.py global-research china
```

SEC requests need `SEC_EDGAR_IDENTITY` in the environment. Tushare needs `TUSHARE_TOKEN` only when its optional second-source connector is enabled. Never put either real value in the repository. Package-profile import checks do not prove provider health; use `uv run --frozen --extra market investment-os doctor --probe daily` for the US/HK daily channels and `uv run --frozen --extra china investment-os doctor --probe china-keyless` for A shares. Stooq is best-effort and may remain unavailable even when its adapter code is installed.

## Clean removal

```bash
cd ..
rm -rf investment-os
```

Removing the checkout removes the project environment and generated output. This repository does not install services, scheduled jobs, or messaging integrations.
