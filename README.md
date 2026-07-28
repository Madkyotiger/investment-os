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
- A completed-brief-only Feishu delivery boundary whose default behavior is a local payload preview, not a network request.
- Boundary tests that reject trade instructions and internal process leakage from reader output.

It is not a brokerage client, portfolio manager, trading bot, autonomous financial adviser, or scheduler. Live delivery is code-gated and disabled by default; no scheduler is included.

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

Run it again with the same `--state` and a different `--out`: the second completed run returns `daily_run=quiet` and does not re-promote unchanged evidence. `--strict` in live mode fails only when no usable live source succeeds; blocked source targets do not by themselves fail a run. See [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

Preview the completed first brief for Feishu without making a network request:

```bash
uv run investment-os deliver \
  --brief .local/daily-evaluation/cxo_daily_brief.md \
  --channel feishu \
  --dry-run
```

The preview is local and does not require a webhook. Quiet or empty completed briefs produce a successful no-send result.

## Agent install

An agent can run the evaluation without changing global Python or system configuration:

```bash
uvx --from git+https://github.com/Madkyotiger/investment-os.git \
  investment-os demo --out ./investment-os-demo
```

For a repository checkout, follow [`AGENTS.md`](AGENTS.md) and [`docs/AGENT_INSTALL.md`](docs/AGENT_INSTALL.md).

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

Some SEC paths require a valid identity string:

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

Tushare requires a token when you use its live connector:

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

## Delivery boundary

Delivery accepts only a `cxo_daily_brief.md` whose bytes match the completed `manifest.json` beside it. It cannot collect sources or update topic state. Dry-run is the default and writes `feishu_delivery_preview.json` locally. Payloads over 20,000 serialized UTF-8 bytes are rejected, live attempts use at most three retries, and HTTP success is accepted only when the Feishu response body also carries application success code `0`.

Live delivery uses an exclusive local file claim around dedup lookup, POST, and receipt write, so concurrent processes sharing the same brief directory do not both send the same payload. This is best-effort deduplication, not exactly-once delivery: if the process or host dies after Feishu accepts the POST but before the local receipt is durably written, a later retry can send a duplicate. Feishu has no transaction with the local receipt, so a human-reviewed destination must tolerate that crash window.

Live Feishu sending is not part of the default workflow. It requires all three conditions: omit `--dry-run`, pass `--confirm-send`, and set `INVESTMENT_OS_ENABLE_LIVE_DELIVERY=true`; the endpoint is read only from `INVESTMENT_OS_FEISHU_WEBHOOK_URL`. Never place that value in a command, config, log, issue, or tracked file. No live send was performed for this implementation.

## Repository boundary

The public repository contains code, synthetic fixtures, sample configuration, tests, and operating documentation. It does not contain personal profiles, holdings, private research, delivery channels, credentials, raw source captures, internal receipts, or local project history.

Run the release guard before every push:

```bash
uv run python scripts/public_release_guard.py
```

## Project status

Version `0.1.0` is ready for installation and evaluation, not unattended production. The next proof is a short human-reviewed test using real daily briefs. Scheduling and live delivery should remain disabled until that test passes and the destination is separately authorized.

The repository does not depend on or vendor FinceptTerminal. No FinceptTerminal code is copied here; external systems may be used only as behavioral comparison points during evaluation.

## License

MIT. See [`LICENSE`](LICENSE).
