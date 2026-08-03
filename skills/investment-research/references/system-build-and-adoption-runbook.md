# Investment Research System Build and Adoption Runbook

### Base-platform selection rule

When the user asks whether to use a mature repo/product as the base, do not choose by stars or by “most complete terminal.” Choose by workflow ownership:

- Data/tooling base: prefer mature integration layers such as OpenBB, plus market-specific sources such as AKShare/Tushare for China.
- Professional-analysis base: prefer transparent calculation/filing tools such as FinanceToolkit and edgartools.
- Research-agent base: use TradingAgents-style analyst / bull-bear / risk roles only after removing Trader, Portfolio Manager approval, execution, and buy/sell language for Phase 1.
- Product-terminal repos such as FinceptTerminal can be benchmarks or independent observation tools, but are risky as the main base when license/commercial terms, maintenance direction, desktop-monolith complexity, or broker/trading scope conflict with a research-only advisory boundary.
- The user's active research system remains workflow owner for schema, evidence ledger, source freshness, client-safe reporting, and no-decision policy. External repos are proven capability modules, not final authority.

### 1. Start by narrowing the objective

If the user asks for an “investment adviser solution,” classify the first phase explicitly:

- information collection;
- analysis;
- risk / missing-evidence surfacing;
- research suggestions;
- no trade decision.

If the user says the solution is for friends or clients too, make the boundary client-safe from the start: disclaimer, no private holdings leakage, no internal paths in external report templates, and no buy/sell/hold phrasing.

### 2. Scan GitHub by capability class, not stars

Use `github-operations` repository landscape mode. Classify repos before scoring:

- data sources and terminals;
- China market data;
- research agents / LLM finance agents;
- quant research and backtesting;
- portfolio optimization and risk;
- execution / live trading;
- dashboards and reporting shells.

Stars are weak evidence. Also check README claims, pushed date, license, data/API dependencies, scope fit, and whether the repo is a full system or a module.

See `references/github-investment-advisor-landscape.md` for the first useful candidate map.

### 3. Build local-first, with hard decision boundaries

For a local reusable solution, create at minimum:

```text
README.md
configs/watchlist.sample.yaml
configs/holdings.sample.csv
docs/00-operating-contract.md
docs/01-solution-architecture.md
docs/02-data-source-routing.md
docs/03-advisory-boundary-and-report-standard.md
docs/04-pilot-plan.md
docs/05-repo-adoption-map.md
templates/advisory-report-template.md
templates/client-intake.md
src/<package>/pipeline.py
tests/test_analysis_policy.py
.gitignore
```

The first runnable tracer bullet should:

- load a watchlist;
- fetch public market data from one simple source such as yfinance;
- compute basic price/risk metrics;
- output Markdown + CSV;
- include tests that fail if research suggestions contain trade-decision wording.

### 4. Verify with real execution

Do not stop after writing docs. Run the current baseline first:

```bash
uv run pytest
uv run python -m <package>.pipeline --config configs/watchlist.sample.yaml --out reports/sample-run
```

When moving to the professional-analysis mainline, run a source-backed tracer bullet before involving LLM agents:

```bash
uv lock
uv run pytest
uv run python -m <package>.spike1_research_memo --symbols AAPL MSFT --out reports/spike-1
```

Then verify:

- sample report exists;
- metrics CSV has rows;
- evidence ledger CSV/JSON exists when using the mainline spike;
- data-quality / freshness counts are stated;
- research suggestion lines contain no buy/sell/hold/add/reduce wording;
- report has a disclaimer and decision boundary.

### 5. Phase adoption carefully

Recommended order:

1. Recurring daily baseline: direct yfinance for configured US/HK watchlist prices, direct SEC/FRED HTTP, official issuer/HKEX research routes, report, and no-decision policy test. Keep package importability, connector configuration, and live probes separate.
2. Optional deep research: add edgartools for complex filing parsing, FinanceToolkit when normalized statement/ratio work earns its maintenance cost, and OpenBB only when it routes to an independent provider rather than wrapping the same yfinance source.
3. China market data: activate AKShare or Tushare when A-share coverage enters scope; use the same Data Quality Gate and retain official PBOC/NBS/CNINFO/SSE/SZSE sources as authority.
4. Research agents: TradingAgents-style analyst / bull-bear / risk only after the evidence layer exists; remove Trader, Portfolio Manager approval, simulated exchange, broker, and execution paths for Phase 1.
5. Portfolio risk: PyPortfolioOpt / Riskfolio-Lib / QuantStats for risk lenses and performance review, not position advice.
6. Quant validation: Qlib / vectorbt / rqalpha as an isolated validation lab.
7. Execution: vn.py / Lean / freqtrade / broker connectors only after explicit approval, dedicated risk controls, and a separate execution service.
