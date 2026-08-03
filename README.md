# Investment OS

[中文说明](README.zh-CN.md)

Investment OS turns market data and source material into research questions, evidence gaps, counter-explanations, and a short reader brief. It is built for agents and humans who want better research discipline without outsourcing the investment decision.

This repository is a public evaluation release. It does not recommend, size, or execute trades.

## What is working

- An offline demo that needs no account, API key, or network access.
- A cross-lane source model for macro, company events, themes, market action, and China/US coverage.
- Evidence states that keep metadata, single-source data, cross-checked data, and source-body reading separate.
- Research questions, counter-explanations, next-source prompts, and kill signals.
- A brief renderer that stays quiet when nothing changed enough to deserve attention.
- An auditable `investment-os daily` runner with explicit watchlist/profile/state paths, source receipts, completed-run manifests, structured failures, and deterministic offline fixtures.
- A keyless `investment-os a-share-daily` path for A-share stocks, with stock/ETF/index routing, price-provider fallback, institutional-holding disclosures, LHB events, block trades, exchange margin data, and a reader-first brief.
- Boundary tests that reject trade instructions and internal process leakage from reader output.

It is not a brokerage client, portfolio manager, trading bot, autonomous financial adviser, scheduler, or messaging client.

## Quick start

You need Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Madkyotiger/investment-os.git
cd investment-os
uv sync --frozen --extra dev
uv run investment-os doctor
uv run investment-os demo --out demo-output
uv run pytest -q
```

The demo writes:

```text
demo-output/
├── market-metrics.csv
├── market-report.md
├── cxo_daily_brief.md
├── cxo_ranked_candidates.json
└── cxo_brief_quality_scan.json
```

A clean demo proves the local package, output path, ranking path, renderer, and boundary scan work together. It does not prove live source availability.

For the full daily path without network access:

```bash
uv run investment-os daily \
  --config configs/watchlist.sample.yaml \
  --profile configs/profiles.sample.yaml \
  --state .local/daily-state.json \
  --out .local/daily-evaluation \
  --offline
```

Run it again with the same `--state` and a different `--out`: the second completed run returns `daily_run=quiet` and does not re-promote unchanged evidence. `--strict` in live mode fails only when no usable fresh live source succeeds; blocked source targets and stale last-known-good observations do not count as current successes. FRED freshness and per-series material-change thresholds, plus the five-calendar-day market snapshot threshold, are explicit in `configs/macro_series.yaml`; the same config is bundled in the wheel for runs outside a checkout. See [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Keyless A-share daily

The A-share path does not require a Tushare token:

```bash
uv run --frozen --extra china investment-os doctor --probe china-keyless
uv run --frozen --extra china investment-os a-share-daily \
  --config configs/a-share-watchlist.sample.yaml \
  --out .local/a-share-daily \
  --strict
```

It writes four files: `brief.md` for the reader, plus `evidence-ledger.csv`, `coverage-matrix.md`, and `source-receipt.json` for audit. `no_event` means a source returned successfully but no matching event appeared in the lookback window; `source_error` means the source was not read. They are never interchangeable.

AKShare is the keyless adapter. The stock-price path falls back from Eastmoney to Sina and Tencent rather than routing a stock through an ETF endpoint. Institutional holdings, LHB, and block-trade rows remain convenience/secondary evidence. SSE/SZSE margin rows are official public data accessed through the adapter, but margin financing still does not identify institutional net flow. Tushare is an optional second-source check; an absent `TUSHARE_TOKEN` does not downgrade the keyless path.

The freshness gate remains five calendar days. A long market holiday can therefore make `--strict` fail closed until a new trading-session row appears; stale data is never relabeled fresh.

## Agent install

An agent can run the evaluation without changing global Python or system configuration:

```bash
uvx --from git+https://github.com/Madkyotiger/investment-os.git \
  investment-os demo --out ./investment-os-demo
```

For a repository checkout, follow [`AGENTS.md`](AGENTS.md) and [`docs/AGENT_INSTALL.md`](docs/AGENT_INSTALL.md).

## Agent skill

The portable skill lives at [`skills/investment-research/`](skills/investment-research/). Copy or link the complete directory into your agent's skill search path, then invoke `investment-research`. The skill adds research discipline and source gates; it does not add credentials, live-source access, scheduling, messaging, or trade execution.

## Optional live market check

Run the market extra in an isolated environment so the project `.venv` stays small:

```bash
cp configs/watchlist.sample.yaml configs/watchlist.local.yaml
uv run --frozen --isolated --link-mode copy --extra market \
  investment-os run \
  --config configs/watchlist.local.yaml \
  --out live-output \
  --strict
```

Strict mode exits non-zero when no symbol has usable fresh-enough data. A generated file is not proof that collection succeeded. The bundled watchlist leaves its `source: china` rows as explicit gaps during this market-only check; it does not send those symbols to Yahoo.

For a recurring live daily runtime, keep only the `market` extra in the project environment and probe the actual channels separately from package imports:

```bash
uv sync --frozen --extra dev --extra market
cp .env.example .env
# Replace the SEC placeholder in .env with a real contact identity.
set -a; source .env; set +a
uv run investment-os doctor --probe daily
```

For an unattended local runtime, `scripts/run_daily_local.sh` first reads `${XDG_CONFIG_HOME:-$HOME/.config}/investment-os/runtime.env` (or `INVESTMENT_OS_ENV_FILE`) and falls back to the ignored checkout `.env`.

`doctor` reports package `importable`, connector `configured`, and `live_probe` as separate facts. OpenBB, FinanceToolkit, edgartools, AKShare, and Tushare are not required by the US/HK-oriented `investment-os daily`; AKShare is required only by `a-share-daily`. Tushare remains optional. Stooq is a best-effort second-source check: a correct adapter path or HTTP 200 is not a successful probe unless usable CSV rows are parsed. The daily runner remains single-source and says so when Stooq is blocked or incomplete.

SEC requests require a valid identity string. It is contact configuration, not an API secret, but real personal contact details still belong in ignored local environment files rather than the public repository:

```bash
export SEC_EDGAR_IDENTITY="Your Name your-email@example.com"
```

## Optional dependency profiles

The public lockfile includes separate profiles for live market data, global research providers, and China data. Check them without adding their packages to the project environment:

```bash
uv run --no-project python scripts/verify_dependency_profiles.py market
uv run --no-project python scripts/verify_dependency_profiles.py global-research china
```

These checks install from the lockfile and import the required packages. They do not call live providers. The first run can take longer while `uv` fills its cache.

Tushare requires a token only when you choose its optional live second-source connector:

```bash
export TUSHARE_TOKEN="..."
```

Never commit credentials or real holdings. Keep them in environment variables and ignored local files.

AKShare and Tushare are convenience/secondary adapters, not official first-party sources. Official China coverage for PBOC, NBS, CNINFO, SSE, SZSE, and HKEX is explicitly incomplete until a stable endpoint is verified and fetched evidence is retained.

## Research boundary

Investment OS can tell you:

- what changed;
- how strong the evidence is;
- what could explain it instead;
- what source to check next;
- what would weaken the working thesis.

It must not tell you to buy, sell, hold, size a position, or execute a trade. Market data can be stale, incomplete, delayed, revised, or wrong. Source metadata proves a document exists; it does not prove the interpretation.

## Artifact handoff boundary

`investment-os daily` writes `cxo_daily_brief.md` beside a completed `manifest.json` that records artifact hashes and run status. That is the handoff boundary. Investment OS does not choose a destination, format a channel payload, hold endpoint credentials, send messages, or manage channel-level retries and deduplication. A downstream runtime may use any channel after independently validating the completed manifest and artifact hash.

## Repository boundary

The public repository contains code, synthetic fixtures, sample configuration, tests, and operating documentation. It does not contain personal profiles, holdings, private research, delivery channels, credentials, raw source captures, internal receipts, or local project history.

Run the release guard before every push:

```bash
uv run python scripts/public_release_guard.py
```

## Project status

Version `0.2.0` adds a real keyless A-share stock path and separates the reader brief from the audit pack. It is ready for installation and human-reviewed evaluation, not unattended production. Scheduling and downstream distribution remain outside this repository.

The repository does not depend on or vendor FinceptTerminal. No FinceptTerminal code is copied here; external systems may be used only as behavioral comparison points during evaluation.

## License

MIT. See [`LICENSE`](LICENSE).
