# GitHub Investment Adviser Landscape — First Candidate Map

Use this map when comparing public repositories for a local, evidence-first investment research system.

## Core judgment

The best first solution is **not** an automatic stock-picking or trading bot. It is an information-first research system:

1. collect data;
2. compute and summarize basic metrics;
3. surface risk and missing evidence;
4. suggest next research actions;
5. leave trading decisions to the human.

## Example public star-list findings

One public GitHub star-list scan contained four repositories:

| Repo | Usefulness |
|---|---|
| `ZhuLinsen/daily_stock_analysis` | Most directly useful ready-made shell for multi-market watchlist reports and Feishu/Telegram/email push. |
| `virattt/dexter` | Useful as a deep financial research agent; not an adviser or execution system. |
| `bannedbook/fanqiang` | Network/proxy related, not an investment repo. |
| `masterking32/MasterDnsVPN` | Network/proxy related, not an investment repo. |

## Repo classes and adoption order

### Phase 1 — data and report shell

| Repo | Role | Notes |
|---|---|---|
| `ZhuLinsen/daily_stock_analysis` | Multi-market stock analysis/report/push shell | A/H/US/JP/KR/TW watchlist, news, AI report, risk alerts, Feishu/Telegram/Slack/email. Good first pilot. |
| `akfamily/akshare` | China/global financial data interface | Useful for A-share, funds, macro, market data. Needs field freshness and source checks. |
| `waditu/tushare` | China stock/financial data | Useful but token/points/license boundaries matter. |
| `OpenBB-finance/OpenBB` | Open data platform for analysts/quants/AI agents | Strong international/global data layer candidate; check license/terms before productizing. |
| `ranaroussi/yfinance` | Quick global market data | Good Phase 1 tracer bullet; should not be the only long-term source. |

### Phase 2 — research agents, not decision makers

| Repo | Role | Notes |
|---|---|---|
| `virattt/dexter` | Autonomous financial research agent | Task planning, data gathering, self-validation. README says educational/informational only; license was not declared during scan. |
| `TauricResearch/TradingAgents` | Multi-agent financial trading research framework | Useful for analyst/researcher/trader/risk-manager debate structure. Treat outputs as hypotheses. |
| `virattt/ai-hedge-fund` | Investor-style agent team | Good for thesis generation and contrarian perspectives; style mimicry can hallucinate. |
| `HKUDS/Vibe-Trading` | Personal trading agent candidate | Ambitious and fast-moving; watchlist/pilot only until runtime, safety, and maturity are proven. |

### Phase 3 — portfolio/risk/performance

| Repo | Role | Notes |
|---|---|---|
| `PyPortfolio/PyPortfolioOpt` | Portfolio optimization | Efficient frontier, Black-Litterman, HRP. Inputs dominate output quality. |
| `dcajasn/Riskfolio-Lib` | Risk-focused portfolio optimization | Useful but parameter-sensitive. |
| `ranaroussi/quantstats` | Portfolio performance analytics | Good for drawdown, Sharpe, Monte Carlo, and reporting. |
| `cvxgrp/cvxportfolio` | Portfolio optimization/backtesting | Technically strong; GPL-3.0 makes distribution/embedding sensitive. |

### Later — strategy validation and execution

| Repo | Role | Notes |
|---|---|---|
| `microsoft/qlib` | AI-oriented quant research | Serious strategy/factor/model research, heavier than a daily advisory front-end. |
| `polakowo/vectorbt` | Fast vectorized backtesting | Great for hypothesis testing; guard against overfitting. |
| `ricequant/rqalpha` | China market backtesting/simulation | Useful for A-share strategy validation. |
| `vnpy/vnpy` | China-oriented quant trading framework | Execution-heavy; defer until explicit live-trading scope. |
| `QuantConnect/Lean` | Professional algorithmic trading engine | Strong, but too heavy for Phase 1 advisory. |
| `freqtrade/freqtrade`, `jesse-ai/jesse` | Crypto trading bots | Defer; pushes solution toward execution. |

## Local scaffold pattern that worked

Project root example:

`<investment-os-repo>`

Useful file set:

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
src/invest_advisor_dataos/pipeline.py
tests/test_analysis_policy.py
scripts/run_sample.sh
.gitignore
```

Test pattern:

- unit tests for missing data degradation;
- unit tests that research suggestions contain no forbidden trade decision wording;
- sample run that generates Markdown + CSV;
- deterministic scan of report suggestion lines for forbidden phrases.

## Forbidden phrase guard

At minimum block suggestion lines containing:

- `建议买入`, `建议卖出`, `建议持有`, `建议加仓`, `建议减仓`;
- `buy`, `sell`, `hold`, `overweight`, `underweight` when they are recommendations.

The report may state the decision boundary itself, e.g. “不输出买入、卖出、持有”, but the generated `Research suggestion` lines must not recommend those actions.
