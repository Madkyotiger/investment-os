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

To check optional package profiles without calling providers:

```bash
uv run --no-project python scripts/verify_dependency_profiles.py market
uv run --no-project python scripts/verify_dependency_profiles.py global-research china
```

SEC requests need `SEC_EDGAR_IDENTITY` in the environment. Tushare needs `TUSHARE_TOKEN`. Never put either value in the repository.

## Clean removal

```bash
cd ..
rm -rf investment-os
```

Removing the checkout removes the project environment and generated output. This repository does not install services, scheduled jobs, or messaging integrations.
