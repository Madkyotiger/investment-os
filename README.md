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
- Boundary tests that reject trade instructions and internal process leakage from reader output.

It is not a brokerage client, portfolio manager, trading bot, or autonomous financial adviser. Scheduling and message delivery are deliberately outside this repository.

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

## Research boundary

Investment OS can tell you:

- what changed;
- how strong the evidence is;
- what could explain it instead;
- what source to check next;
- what would weaken the working thesis.

It must not tell you to buy, sell, hold, size a position, or execute a trade. Market data can be stale, incomplete, delayed, revised, or wrong. Source metadata proves a document exists; it does not prove the interpretation.

## Repository boundary

The public repository contains code, synthetic fixtures, sample configuration, tests, and operating documentation. It does not contain personal profiles, holdings, private research, delivery channels, credentials, raw source captures, internal receipts, or local project history.

Run the release guard before every push:

```bash
uv run python scripts/public_release_guard.py
```

## Project status

Version `0.1.0` is ready for installation and evaluation, not unattended production. The next proof is a short human test using real daily briefs. Cron and automated delivery should wait until that test passes.

## License

MIT. See [`LICENSE`](LICENSE).
