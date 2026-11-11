# Investment OS

[中文说明](README.zh-CN.md)

Investment OS exists to give its reader enough of the information that could change an investment decision: what changed, how strong the evidence is, what is still missing, and the strongest counter-explanation. The judgment stays with the reader.

This repository is a public evaluation release. It does not recommend, size, or execute trades.

Investment OS is multi-market by design. The existing `daily` watchlist path continues to cover U.S. and Hong Kong equities, market proxies, macro context, and other configured sources. `a-share-daily` is an added A-share lane, not a replacement for those paths and not a boundary on future markets or source types.

## What is working

- An offline demo that needs no account, API key, or network access.
- A cross-lane source model for macro, company events, themes, market action, and China/US coverage.
- Evidence states that keep metadata, single-source data, cross-checked data, and source-body reading separate.
- Research questions, counter-explanations, next-source prompts, and kill signals.
- A brief renderer that shows every change that clears the evidence gate, with no fixed item count, and stays quiet when nothing did.
- An auditable `investment-os daily` runner with explicit watchlist/profile/state paths, source receipts, completed-run manifests, structured failures, and deterministic offline fixtures.
- The daily radar (`investment-os radar`): the path a real daily brief runs on. An agent researches and writes; the program supplies the history, verifies every cited source, tracks open questions, stores the run, and reports what the runs collected. See [`docs/RADAR.md`](docs/RADAR.md).
- A keyless `investment-os a-share-daily` path for A-share stocks, with stock/ETF/index routing, price-provider fallback, institutional-holding disclosures, LHB events, block trades, exchange margin data, and a reader-first brief.
- An on-demand public expert/media catalog and `source-plan` resolver that selects a minimal capture plan from explicit topics, geographies, viewpoint roles, access permissions, and limits.
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

Run it again with the same `--state` and a different `--out`: the second completed run returns `daily_run=quiet` and does not re-promote unchanged evidence. In live mode a market move is material when it exceeds twice that symbol's own trailing 60-day daily volatility, and a daily bar is used only after its exchange has closed. `--strict` in live mode fails only when no usable fresh live source succeeds; blocked source targets and stale last-known-good observations do not count as current successes. FRED freshness and per-series material-change thresholds, plus the five-calendar-day market snapshot threshold, are explicit in `configs/macro_series.yaml`; the same config is bundled in the wheel for runs outside a checkout. See [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

## Daily radar

`investment-os radar preflight | evaluate | store | collection-report` is the agent-researched path: the agent finds and reads sources and writes the brief, and the program checks the evidence packet it brings back. Nothing is published when coverage is incomplete and nothing qualifies, every qualifying item is kept, and open questions stay open until evidence closes them. `collection-report` summarizes what recent real runs could and could not collect; recurring gaps in that report are what drive new collectors and source routes in this repository. Commands, the packet format and the rules are in [`docs/RADAR.md`](docs/RADAR.md).

## On-demand expert and media source plan

The shared catalog is not a subscription list and does not scan every source by default. A caller must provide a concrete research need and explicit access permissions:

```bash
uv run investment-os source-plan \
  --catalog configs/public_source_catalog.json \
  --request configs/source_request.sample.yaml \
  --out .local/source-plan.json
```

The output is a capture plan, not evidence. Expert and media material remains discovery, context, mechanism, consensus, or counterview input; consequential facts still require primary or auditable sources. Every request carries a `candidate_source_ids` allowlist so a reader's source pool cannot expand silently when the shared catalog grows. Sources marked `explicit_need_only` require both an explicit source ID and `allow_explicit_need_only: true`. Missing access permissions fail closed, and unavailable or unconfigured channels are never returned as active capture routes.

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

The freshness gate remains five calendar days. A long market holiday can therefore make `--strict` fail closed until a new trading-session row appears; stale data is never relabeled fresh. Before 15:05 Shanghai time the brief uses the last finished session, not the current intraday quote. Its direction sentence is counted from institution-seat net amounts and says so when no directional data exists.

## Agent install

An agent can run the evaluation without changing global Python or system configuration:

```bash
uvx --from git+https://github.com/Madkyotiger/investment-os.git \
  investment-os demo --out ./investment-os-demo
```

For a repository checkout, follow [`AGENTS.md`](AGENTS.md) and [`docs/AGENT_INSTALL.md`](docs/AGENT_INSTALL.md).

## Agent skill

The portable skill lives at [`skills/investment-research/`](skills/investment-research). Copy or link the complete directory into your agent's skill search path, then invoke `investment-research`. The skill adds research discipline and source gates; it does not add credentials, live-source access, scheduling, messaging, or trade execution.

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

`doctor` reports package `importable`, connector `configured`, and `live_probe` as separate facts. AKShare and Tushare are not required by the US/HK-oriented `investment-os daily`; AKShare is required only by `a-share-daily`. Tushare remains optional. Market prices in `daily` come from one source (Yahoo Finance through yfinance) and are labelled single-source in the brief.

SEC requests require a valid identity string. It is contact configuration, not an API secret, but real personal contact details still belong in ignored local environment files rather than the public repository:

```bash
export SEC_EDGAR_IDENTITY="Your Name your-email@example.com"
```

## Optional dependency profiles

The public lockfile includes separate profiles for live market data and China data. Check them without adding their packages to the project environment:

```bash
uv run --no-project python scripts/verify_dependency_profiles.py market
uv run --no-project python scripts/verify_dependency_profiles.py china
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

Version `0.2.2` repairs the live `daily` path, which stopped without output whenever a monthly macro release reached the brief; shows every qualifying change instead of the first five; judges market moves against each symbol's own volatility on closed sessions; and retires the early pilot modules with their `global-research` dependency profile. It is ready for installation and human-reviewed evaluation, not unattended production. Scheduling and downstream distribution remain outside this repository.

The repository does not depend on or vendor FinceptTerminal. No FinceptTerminal code is copied here; external systems may be used only as behavioral comparison points during evaluation.

## License

MIT. See [`LICENSE`](LICENSE).
