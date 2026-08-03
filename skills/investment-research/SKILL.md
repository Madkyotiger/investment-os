---
name: investment-research
description: Build and operate evidence-first investment research systems. Use when the task involves source-backed market research, watchlists, data pipelines, evidence ledgers, longitudinal issuer analysis, risk review, or reader briefs. Do NOT use for buy/sell/hold calls, position sizing, brokerage execution, or regulated investment advice.
version: 2.2.0
author: Investment OS contributors
license: MIT
compatibility: hermes
metadata:
  hermes:
    tags: [investment-research, finance, data-pipeline, advisory-boundary, portfolio-risk, github-landscape]
    related_skills: [github-operations, software-development-lifecycle, current-state-docs, financial-content-benchmarking]
---

# Investment Research

## Purpose

Build reusable investment information systems that help the user collect, clean, analyze, and discuss market information without pretending to be a licensed investment adviser or an automatic trading brain.

Default stance:

> The system may give research suggestions. It must not make trading decisions.

This skill is for solution design and local/system implementation, not for giving financial advice in chat.

## When to Use

Use when the user asks to:

- research GitHub repos for personal investment, finance, trading, robo-advisory, quant, portfolio, or market-data workflows;
- build a local investment research solution for themselves, friends, or clients to reference;
- create a watchlist / holdings / market data pipeline;
- structure outputs as research notes, risk checks, or client-safe reports;
- connect tools such as AKShare, Tushare, OpenBB, yfinance, daily_stock_analysis, Dexter, TradingAgents, PyPortfolioOpt, Riskfolio, QuantStats, Qlib, vectorbt, rqalpha, vn.py, Lean, freqtrade, or similar repos;
- create reusable Hermes skills/templates for investment research workflows.

Do NOT use to provide direct buy/sell/hold recommendations, position sizing, promises of return, or regulated investment advice.

## Core Boundary

The system can say:

- 建议补充哪些证据;
- 建议优先研究什么;
- 建议关注哪些风险;
- 建议设置哪些复盘触发条件;
- 建议对组合集中度/回撤/波动做检查;
- 建议做反方 thesis 或验证数据源。

The system must not say:

- 建议买入 / 卖出 / 持有;
- 建议加仓 / 减仓 / 清仓;
- 保证收益 / 确定机会 / 适合所有人;
- 自动下单或接券商执行 as a Phase 1 default.

## Recommended System Shape

For the user's first-pass solution, prioritize a proven workflow mainline rather than a single large terminal repo or ad-hoc stitching:

```text
Watchlist / Holdings / Client Intake
        ↓
Data & Tooling Base
  - Recurring US/HK daily: direct yfinance market path + direct SEC/FRED HTTP; official issuer/HKEX pages remain primary research routes
  - Second-source market check: Stooq only when a live probe returns usable same-date rows; otherwise keep single-source status
  - Optional deep research: OpenBB for genuinely independent provider routing, FinanceToolkit for normalized ratios, edgartools for complex filing parsing
  - China branch: use AKShare as the keyless adapter when A-share coverage is in scope; use Tushare only as an optional credentialed second source; official PBOC/NBS/CNINFO/SSE/SZSE sources remain authoritative
        ↓
Data Quality Gate
  - source
  - as_of_date
  - freshness
  - fallback
  - missing / stale / conflicting fields
        ↓
Evidence Ledger
  - fact
  - source-backed metric
  - filing / event metadata or quote
  - model interpretation
  - hypothesis
  - missing evidence
        ↓
Professional Analysis Engines
  - FinanceToolkit: statements, ratios, valuation / peer comparison where available
  - edgartools: SEC 10-K / 10-Q / 8-K / Form 4 / 13F metadata and links
  - macro context: fredapi / OpenBB macro
        ↓
Research Committee（去交易化）
  - TradingAgents-style analyst / bull-bear / risk roles only after evidence exists
  - no Trader, Portfolio Manager approval, broker, simulated exchange, or execution in Phase 1
        ↓
Portfolio Risk Layer
  - PyPortfolioOpt / Riskfolio-Lib / QuantStats
        ↓
Client-safe Research Memo
  - facts, interpretation, risks, bear case, evidence gaps, research suggestions, no decision
```

For the optional OpenBB + FinanceToolkit + edgartools deep-research tracer bullet, see `references/source-backed-mainline-spike.md`. It is not the recurring daily dependency baseline.

For the US-first + China-parallel unified pilot pattern, see `references/us-china-unified-pilot.md`.

For public expert signals from X/newsletters/research blogs — especially US equities, AI infrastructure, semiconductor bottlenecks, capex/FCF stress, and valuation counterviews — use `references/expert-signal-crosswalk.md` before promoting any opinion into the Evidence Ledger or an external note.

For the user-facing investment output style, two-tier reports, anti-AI Chinese finance phrasing, and non-AI-only source-universe routing, use `references/investment-output-style-and-source-universe.md`.

Before writing or repairing any recurring Investment OS reader artifact, lock the product seat with `references/daily-scan-vs-triggered-rolling-deep-read.md`: Product A Daily Scan for broad current browsing; Product B Triggered Rolling Deep Read only when a decision-worthy current change can be compared against longitudinal history and carried to the next material event. Product B depth comes from longer memory and sharper delta analysis, not a narrower fixed question or a six-to-twelve-month forecast. A Stock/Question Deep Pack remains an on-demand special-study mode when the user explicitly asks and source coverage is sufficient. AI's leverage is multi-source cross-check, historical comparison, BOM/supplier expansion, consensus/disagreement and falsifiers under human command.

For executing a real Product B event, use `references/triggered-rolling-deep-read-runbook.md`: require a current delta, a roughly twelve-month comparable history floor, a named next material event and a concrete research action; close missing issuer history before writing; separate reported and derived figures; and keep finite Product A pilots deduplicated, quota-free and time-boxed.

When a C 超 personal-investor brief is readable and source-correct but still feels shallow, generic, or borrowed, use `references/cxo-house-view-and-viewpoint-synthesis.md`: audit whether named architecture components are actually wired into runtime, compare published items to the same-run Evidence Ledger, separate classification from judgment generation, then build a Thesis Delta Card, expectation baseline, competing lenses, and falsifiable House View before adding more sources or agents. The resulting implication must land on earnings, cash flow, valuation, cycle, asset exposure, or risk—not corporate budget/vendor actions.

When the research class depends on filings, earnings calls, long-form sell-side/professional reports, or prior forecasts, use `references/longitudinal-research-memory-system.md`: build Source Artifact / Event / Claim / Thesis state, compare the new source against genuinely comparable historical claims, preserve access rights and the event/context clocks, and prove value with a single-document-summary versus comparative-read Gold Sample before implementing the full system.

When the user changes a Product B forecast quarter or the compared issuers use different fiscal calendars, use `references/forecast-horizon-and-fiscal-period-alignment.md`: separate source cutoff, target decision horizon, issuer fiscal mapping, and structural stress horizon; build the Model Gate as a falsifier; separate mechanics from attribution; distinguish price level from rate of change; treat HBM as a wafer-allocation/opportunity-cost variable rather than automatic margin uplift; reconcile parallel audit writebacks; update Scope/Matrix/Receipt/Current/validator together; and do not rewrite long-range evidence as if it directly proves the new target quarter.

When a bounded special study ends at `PARTIAL PASS / HOLD`, use `references/model-gate-hold-to-falsifier-dashboard.md`: freeze the validated model and receipt; turn only judgment-changing gaps into an event-driven Falsifier Dashboard; rerun the same model only on predeclared issuer, contract, consensus, price, or FCF triggers. The dashboard and any Research Gate Brief are backend/method assets unless a fresh current event earns a new Rolling Deep Read; do not make missing evidence a recurring reader update. Audit live scheduler prompts against the latest accepted reader/product contract during handoff.

When a sector can be read through a few high-information companies and their upstream/downstream relationships, use `references/anchor-company-network-research.md`: start with the smallest demand/manufacturing/competitor/challenger spine, compare identical variables across aligned quarters, add only one gap-driven edge node, and treat prominent CEO narratives as Viewpoints that require independent confirmation.

Before promoting the comparison into a network Thesis Delta or House View, use `references/cross-node-thesis-delta-audit.md`: distinguish separate issuer disclosures from independent end-demand confirmation, require semantic citation closure for every old/new component, separate historical realization from persistence/customer-side tests, map constraint stacking to `silicon-ready → rack-shipped → energized → utilized → monetized`, and choose the next edge node by one predeclared thesis-reversal test.

When that edge node is a hyperscaler or customer-side infrastructure operator, use `references/hyperscaler-capex-to-economics-conversion-bridge.md`: predeclare one three-quarter CapEx / depreciation → accounting activation or deployment → segment economics → cash-recovery bridge; keep in-service assets as accounting proxies rather than energized-capacity proof; distinguish `BRIDGE STRENGTHENED`, `LAG OR DETERIORATION`, and `DISCLOSURE GAP`; and preserve backlog, acquisition, transcript, merchant-silicon, customer-ROI, and company-cash boundaries before writeback.

When an approved anchor pilot moves into source collection—especially in a fresh session—use `references/anchor-network-source-collection-contract.md`: update project state from pending to active, create the expected-slot manifest before bulk download, resolve real fiscal periods from official sources, collect in verified tranches, preserve raw files/hashes/access states, and stop at a coverage receipt before analysis. For any issuer’s official quarterly earnings corpus, use `references/issuer-ir-sec-earnings-corpus-recon.md`: select the three latest *reported* quarters as-of the cutoff, enumerate IR Related Documents, pair IR releases with SEC 8-K / 10-Q / 10-K anchors, distinguish prepared remarks from full Q&A, separate `official_url` from the archived `readable_url`, preserve lower provenance for registration-gated call fallbacks, and verify immutable files/hashes before the receipt. For the NVIDIA-specific official IR + SEC route—including the Q4-backed event API, 8-K Exhibit 99.1/99.2 routing, registration-gated webcast handling, and exact time-state discipline—also use `references/nvidia-ir-sec-source-recon-pattern.md`.

For **Korean-listed / KRX issuers** (worked example: SK hynix) where the US 8-K/10-Q path does not apply, use `references/korea-issuer-ir-earnings-corpus-recon.md`: map IR Earnings Release / Audit Report / ESG Financing surfaces, keep newsroom `official_url` separate from IR CDN PDF or issuer-SOURCE wire `readable_url` when newsroom returns 403, never treat ESG “Annual Report” as K-IFRS financial annual report, separate preliminary earnings vs independent review vs year-end audit, and leave conference-call entries without an independent transcript as explicit absence.

Before defining or repairing a CXO financial brief, load `financial-content-benchmarking`: inspect recent complete media editions, then use its benchmark-to-delivery gate and `templates/cxo-financial-brief.md`. Do not redesign the reader surface from internal taste after a failed sample.

For turning investment research into a C 超 personal-investor push — broad source candidates, personal-investment relevance, asset/watchlist context, reader-specific ranking, falsifiers, and next research triggers — use `references/cxo-personal-intelligence-layer.md`. C 超 identity is analytical context, not corporate decision authority; never turn it into budget, vendor, team, or operating instructions.

For the implemented pattern that adds topic state, source-universe ranking, CXO relevance, watchlist routing, and first-pass hard-source rows such as SEC ticker/CIK identity, Fed calendar, and Treasury source targets, use `references/cxo-hard-source-change-tracking-layer.md`.

For upgrading a pilot source-universe / topic-state system into a live hard-source CXO feed — SEC recent filing metadata, FRED yield-curve values, market proxy moves, watchlist relevance routing, and runner verification markers — use `references/live-hard-source-cxo-collector.md`.

For the mandatory product-utility gate when tests are green but the brief may not be useful — three real-date Gold Samples, meaningful-change selection, duplicate suppression, filing relevance, local time, lane coverage receipts, and bad-output fixtures — use `references/product-utility-acceptance-gate.md`.

For the downstream implementation pattern — structured research-question cards, thesis-key deduplication, fresh-evidence + explicit-impact gating, quiet-state output, honest coverage receipts, primary-source number reconciliation, and timezone-aware historical replay without future-data leakage — use `references/judgment-kernel-and-historical-replay.md`.

When evaluating an external investment-methodology repo that promises better judgment through personas, multi-agent debate, checklists, reports, or audit tools, use `references/external-investment-methodology-repo-audit.md`: inspect current remote truth and real outputs, separate reusable functions from authority theater, adversarially probe numeric/audit claims, and adapt only the mechanisms that serve the evidence/question-layer objective.

## Source-Bounded Filing / Earnings Claim Cards

When a user asks for source-anchored atomic claims from a bounded issuer earnings corpus or annual filing:

1. Lock the allowed local source paths and preserve the normalized source path on every card; do not supplement with search snippets, web summaries, prior quarters, or inferred market data.
2. Split disclosed financial facts, issuer outlook, risk disclosure, management explanation, management judgment, and Q&A non-answer into separate cards. A stated metric does not prove management's causal explanation.
3. Each card must carry: draft claim ID, claim type, metric/variable, period/horizon, an unedited English quote, exact normalized line range, source provenance, `cannot_prove`, and a page field. For HTML/SEC sources, state `PDF page: N/A (HTML)` and include a printed filing page only if visible in the normalized text—never fabricate pagination.
4. Preserve provenance distinctions: SEC-filed Form 10-K; furnished 8-K exhibit; issuer CFO commentary; issuer IR-hosted provider-corrected transcript; and issuer presentation are different source classes. An IR-hosted provider transcript is not automatically issuer-authored or word-perfect.
5. For Q&A, record the exact question, quantitative/directional answer, explicit unanswered/deferred scope, and stated timeline. “Unanswered” means missing from that answer, not misconduct.
6. Finish thesis notes as three distinct layers: facts, management judgment/outlook, and unknown. Do not convert this evidence layer into a cross-quarter conclusion or investment recommendation.
7. When parallel quarter extractions return, preserve them as issuer-level audit material under one `extractions/<issuer>/` directory; do not let worker reports, alternate IDs, or stray `reference-md/claims/` paths become a second canonical ledger.
8. Reconcile selectively. Promote only claims that change judgment, accountability, a falsifier, or the next verification route. Generate each promoted anchor quote directly from its normalized source line range, then rebuild the canonical ledger and dossier.
9. Keep capital-linkage fields non-additive unless the filing supplies a reconciliation: inventory, supply/capacity commitments, own-use cloud commitments, book investments, investment commitments, infrastructure guarantees, management `total supply`, and mismatch provisions are different accounting or contractual objects. Linkage does not prove backlog, independent demand, or circular revenue.
10. Treat new-product revenue/visibility figures as management commitments until standalone/integrated overlap, incrementality versus cannibalization, recognized revenue, deployment, and supply are separated. A use-case explanation is not an answer to an overlap question.
11. Apply an issuer-first fact hierarchy. Reported results and formal guidance anchor to issuer releases/reports/presentations; accounting and contractual facts anchor to filings; provider-edited transcripts anchor management wording, Q&A, non-answers, estimates, and timetables. Do not use transcript convenience to lower fact authority.
12. Treat denominator mismatches as claims. Preserve whether `HPC`, `AI accelerator`, data-center CPU, advanced packaging, system supply, customer investment, and issuer revenue include different components before cross-company comparison.
13. Detect plan drift rather than adjective drift. A changed fab/node allocation, CapEx range, production date, capacity horizon, or disclosed quantity matters; stronger confidence language alone does not.
14. Close in this order: final edits → deterministic validation → artifact hashes → receipt → receipt-hash verification → Current/private-state event writeback → readback. Never hash or declare state before the last artifact edit.
15. Normalize and index before extraction. Let the normalized index determine the actual fiscal periods, source slots, files, URLs, hashes, publisher times, source classes, and transcript provenance; do not hand-select periods from filenames or remembered calendars.
16. Treat filing amendments as field-level authority changes. Preserve the original filing as `superseded_filing_text` provenance, anchor the amendment purpose and corrected wording separately, use only amended values in current claims/dashboards, and make the validator assert both old and corrected values.
17. For multi-role issuers, separate products, internal manufacturing, external foundry commercialization, and policy/strategic capital before synthesis. Segment manufacturing revenue is not external foundry demand; government or strategic equity is not a wafer order; captive fabs do not erase third-party/Taiwan supply dependence.
18. After parallel packets PASS the quote verifier, still enforce a company-specific required-evidence gate and canonicalize heterogeneous card IDs into one ledger namespace. Packet literalness is necessary, not sufficient.

For the full reconciliation route, issuer-first source hierarchy, definition/denominator audit, amendment-authority handling, deterministic receipt order, capital-linkage field map, and NVIDIA/TSMC/AMD/Intel calibrations, use `references/company-baseline-reconciliation-and-capital-linkage.md`.

## Chat Trigger Contract

When the user wants to run this from the conversation instead of terminal, accept natural Feishu/DM triggers and execute the corresponding local pipeline without asking for shell commands:

- `跑投研简报` / `更新投研简报` / `今天的投研简报` → run the current full local pipeline, return the phone-screen brief in chat, and mention the detailed pack path only as a compact receipt.
- `只刷新投研读者版` / `只重生成简报` → rerender the detailed pack + daily brief from the existing ledger/queue, without rerunning source collection.
- `看详细版` / `展开详细版` → read and summarize or return the detailed pack.
- If the user says `完整报一遍` / `完整跑一遍` / `不足的信息先补齐`, treat it as a higher bar than a lightweight brief: first locate and read the live project/handoff/README if available, run the current verified pipeline, read back the generated brief + detailed pack + quality scans, then supplement gaps with fresh public-source searches. Do not present a merely hand-written market summary as “Investment OS” output.
- If the user says `跑全市场简报`, only do this after a source-universe collector exists; until then state that the current runnable pipeline is the AI-infrastructure pilot and the broader source universe is routing design, not live ingestion.

Default chat delivery: paste the daily brief first for normal daily triggers. For `完整` / gap-filling requests, lead with the investment judgment, then include a compact verification receipt: pipeline/test result, evidence-row count, quality-scan status, and the remaining unfilled source gaps. Keep terminal logs out of chat; include detailed file paths only as compact receipts when useful.

## Strict Current-Intelligence Source Gate

Use this gate whenever a daily/CXO investment brief is constrained to an exact interval.

1. Declare the UTC start/end before collecting. Preserve event time, publisher timestamp, and normalized UTC time separately; a same-day recap of an older filing, launch, or lawsuit is not a fresh item.
2. Fully read the source body. Search snippets, paywall previews, and social reposts are locator-only and must be excluded or recorded as blocked.
3. Prefer the original publisher. If it is blocked but an explicitly attributed, complete licensed/syndicated copy is readable, use that reprint for the reported claim; record the original URL, readable URL, and access limitation.
4. Reconcile decision-changing claims with the strongest available first source — company filing/release, regulator, government, official account, or official union/industry body. State the narrow proposition that source confirms; do not let it certify broader causality or risk removal.
5. If the evidence bar leaves fewer worthy items than the requested quota, publish the smaller set and an exclusion note. Never pad with older events or unverified summaries. On weekends, holidays, and thin-news windows, a one-item result or no reader-facing push is a successful outcome when the gate is met.
6. Produce a machine-side source audit for every decision-relevant candidate: title, publisher timestamp, underlying event time where known, original URL, readable/syndicated URL if different, access state, evidence strength, and the specific inclusion/exclusion reason. An unsuccessful scan of regulator/company/filing domains is coverage evidence only—write “not found in this scan,” never “no event occurred.”

## Workflow

### Base-platform selection rule

When the user asks whether to use a mature repo/product as the base, do not choose by stars or by “most complete terminal.” Choose by workflow ownership:

- Data/tooling base: prefer mature integration layers such as OpenBB, plus market-specific sources such as AKShare/Tushare for China.
- Professional-analysis base: prefer transparent calculation/filing tools such as FinanceToolkit and edgartools.
- Research-agent base: use TradingAgents-style analyst / bull-bear / risk roles only after removing Trader, Portfolio Manager approval, execution, and buy/sell language for Phase 1.
- Product-terminal repos such as FinceptTerminal can be benchmarks or independent observation tools, but are risky as the main base when license/commercial terms, maintenance direction, desktop-monolith complexity, or broker/trading scope conflict with a research-only advisory boundary.
- The local DataOS remains workflow owner: schema, evidence ledger, source freshness, client-safe report, and no-decision policy. External repos are proven capability modules, not final authority.

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

## Output Standard

Every report should contain:

- scope;
- data sources and freshness;
- market snapshot;
- observations;
- risks and evidence gaps;
- research suggestions;
- decision boundary;
- fixed disclaimer.

Default disclaimer:

> 本报告只用于信息整理、研究讨论和风险提示，不构成投资建议、交易建议或收益承诺。市场有风险，任何交易决策应由使用者基于自己的风险承受能力、资金期限、税务/法律情况和独立判断作出。报告中的数据可能延迟、缺失或有误，请在行动前自行核验。

## Pitfalls

1. **Accidentally building a trading bot.** If the first phase connects execution, broker auth, or auto-ordering, scope has drifted. Push execution to a later explicit phase.
2. **LLM-as-adviser smell.** LLM outputs must be treated as research hypotheses or summaries, never final advice.
3. **Star-count trap.** Popular finance repos can be hype-heavy; lower-star data libraries can be more useful.
4. **Single-source data confidence.** Public APIs can be stale, delayed, adjusted differently, or license-limited. Always surface data freshness and evidence gaps.
5. **Client-safe template leakage.** External templates must not expose the reader's private holdings, local filesystem paths, internal repo names, or unreviewed conclusions.
6. **Optimizer theater.** Portfolio optimizers produce precise-looking outputs from fragile assumptions. Treat them as risk lenses, not answers.
7. **China-source endpoint fragility.** AKShare endpoints do not fail uniformly: Eastmoney history may fail behind a proxy while Sina or Tencent stock history still works. Route `stock`, `etf`, and `index` explicitly; never send an A-share stock to an ETF endpoint. For stock history, use a bounded Eastmoney → Sina → Tencent fallback chain and retain the actual source. The keyless A-share path uses AKShare; absent `TUSHARE_TOKEN` is `optional_source_not_configured`, not a failed or degraded run.
8. **SEC section parsing variance.** edgartools markdown is useful for 10-K/20-F section detection, but headings vary by issuer: some filings expose `## Item 1`, others omit heading markers or only show table-of-contents rows. Use `filing.markdown()` plus `filing.sections()` as a dual path; cache SEC markdown/section chunks locally; treat section detection as an Evidence Ledger field with `section_found` / explicit gaps. Do not claim a section was deeply analyzed unless the parser actually found the section body.
9. **China dual-source reconciliation.** Only claim reconciliation when AKShare and credentialed Tushare evidence both exist. If Tushare is not configured, retain an explicit `optional_second_source_not_configured` row but do not count it as a gap or block the keyless path. When both sources exist, compare at least trade date and close before upgrading a downstream summary.
10. **Peer-set context is not peer-set judgment.** For US-first pilots, put the default peer map into Evidence Ledger rows such as `peer_set_context` with close/60D/1Y and a local map source. Then add `peer_financial_context` rows for ratios such as market cap, PE, P/B, margin, revenue growth, debt/equity, and current ratio. Keep both as context lenses until business comparability, filing risks, and source methodology are checked; do not turn relative price movement or ratio gaps into a recommendation.
11. **Filing excerpts are evidence, not interpretation.** Once section detection works, add `filing_excerpt` rows with short raw excerpts from the detected section body. Keep excerpts clearly labeled as raw source text for researcher review; do not summarize beyond the source or imply the filing has been fully analyzed.
12. **Theme snippets need table-noise filtering.** If you promote filing excerpts into `filing_theme_snippet` rows, select keyword-dense raw sentences for themes such as business_model, risk_factor, and performance_driver, but filter statement tables / table-of-contents fragments / markdown pipe tables before choosing snippets. A keyword hit inside an income-statement table is not a useful performance-driver snippet.
13. **Review rules must remain questions.** When turning peer tables and filing snippets into next-step analysis, emit categories such as `peer_review_question` and `filing_review_question` with explicit research/red-flag questions, not conclusions. For peer rules, split subtypes instead of writing one generic prompt: valuation-vs-quality, balance-sheet comparability, growth/margin quality, and source-methodology checks. Let valuation / balance-sheet / growth-margin questions be threshold-triggered by metric spread; keep source-methodology as a comparability guard when runtime/vendor fields have mixed definitions or missing coverage. For filing snippets, keep the evidence basis inside the question sentence, not as a conclusion. Mark rows `partial` / derived from evidence so they cannot masquerade as source facts or trade advice.
14. **External report templates are not pilot logs.** Friend/client-facing templates should include disclaimer, source freshness, evidence ledger summary, evidence gaps, research questions, and decision boundary, while excluding local paths, cache paths, run commands, repo names, and implementation noise. Test the template for decision-language and local-path leakage before treating it as forwardable.
15. **External note renderers need their own QA gate.** Once a pilot ledger can produce an internal memo, add a separate external renderer that reads evidence rows and writes a forwardable research note. Pair it with a deterministic quality scan for local paths, cache paths, run commands, implementation labels, and decision/execution language. Keep real source failures visible in the audit pack; do not pollute the reader brief with optional connector configuration such as an absent Tushare token.
16. **Expert signals are lenses, not conclusions—and ingestion cannot be the final stage.** X/newsletter/public expert posts can improve the research frame, especially for US equities, AI infrastructure, semiconductor bottlenecks, valuation assumptions, capex/FCF stress, and counterviews. Default them to weak/probable opinion evidence until linked sources or primary data are inspected. At ingestion, use categories such as `expert_signal_context`, `expert_counter_signal`, `expert_signal_gap`, and `expert_signal_review_question`; external notes must tie each signal to evidence support/conflict/gaps and block hype/social-pump language such as 10x/10倍/20倍, “韭菜/收割/跟着机构”, or certainty/opportunity slogans. But do not stop at “question fuel only”: once the evidence is verified, place one strong supporting interpretation and one strong counterview into a judgment step, extract their assumptions and falsifiers, and form a bounded House View that still stands when the famous names are removed. A quote stream is not synthesis.
17. **Expert signal ingestion needs a separate gate.** When a public expert seed becomes repeatable, normalize it through an `expert_signal_ingest`-style step before merging with the main Evidence Ledger: validate required columns, keep rows `partial` unless primary evidence is inspected, turn review rows into questions, render `Public Expert Signal Crosswalk`, and run an external-note quality scan. The crosswalk should show `Signal → Evidence support/conflict/gap → Research question → Next source`, not “expert says therefore”.
18. **Source verification upgrades only narrow claims.** After expert signals enter the ledger, run a `source_verification_crosswalk`-style gate before treating them as observations: source rows need auditable URLs, source type, source date, evidence direction (`support/counter/gap/mixed`), strength (`verified/probable/weak/blocked`), what the source verifies, what remains unproven, next action, and status. Categories such as `expert_source_verification` and `expert_source_gap` belong in the main Evidence Ledger. A source row can verify “NVIDIA discloses full-stack infrastructure” or “Murata says AI servers increase capacitor count”; it cannot prove timing, shortage duration, supplier economics, or company exposure unless those are separately sourced.
19. **Unresolved source checks become a timed queue.** Do not let `missing`, `partial`, `gap`, `mixed`, `weak`, or `blocked` source-verification rows disappear into report caveats. Convert them into source-check tasks with priority, cadence, next check date, source targets, and close criteria. P0 gaps should stay open until a new auditable source row with `source_url`, `source_date`, `evidence_excerpt`, `cannot_prove`, and `next_action` passes the quality scan. A queue is still a research-action layer, not a scheduled trade or recommendation.

20. **The reader surface is a personal-investment hypothesis update, not a pipeline receipt or fixed-quota news list.** Evidence ledgers, source-verification crosswalks, queues, coverage counts, local files, claim IDs, and quality scans remain backend infrastructure. Default delivery is 1–4 decision-worthy changes and may be shorter; do not target five because an old template did. Use one market thesis only when the items share an earned economic mechanism. Each item should compress one hard fact, the prior view, the evidence-crossed read, the personal-investment implication, and a falsifier or next decisive check. The implication must land on earnings, cash flow, valuation, cycle, profit capture, asset/watchlist exposure, or risk—not company budget, vendor choice, team action, or operating projects. Do not expose template/system language or unnecessary English. If there are zero worthy items, send nothing. Engineering green is not product acceptance: the named reader must understand the short brief in 15–30 seconds and find that it changes what they investigate, monitor, or treat as risk next. Use `financial-content-benchmarking` before locking the format, and use `references/cxo-house-view-and-viewpoint-synthesis.md` when the output is readable but lacks depth or a distinctive point of view.

21. **AI infrastructure is a pilot topic, not the source universe.** Daily investment intelligence should select from a broad source universe: macro regime, company events, sector/theme discovery, market action, expert/media signals, and portfolio/watchlist relevance. Rank items by decision usefulness, evidence change, novelty, magnitude, source quality, and portfolio relevance. Exclude repeated themes without new evidence, uncheckable opinion, pure hype, and trade instructions. A daily brief should surface the most useful changes across the whole source universe, not repeat a fixed theme because the first renderer was built on AI infrastructure.

22. **C 超个人投研不是公司高管行动简报。** 在本系统里，C 超指以个人身份阅读投资、理财和财经内容的高认知个体；职业身份只提供理解背景。Build/rank source-universe candidates, apply personal-investment interests and asset/watchlist exposure, then render only 1–4 items as changes in earnings, cash flow, valuation, cycle, profit capture, asset exposure, or risk, with a next research trigger and downgrade signal. A market item becomes push-worthy only when it changes the reader's personal investment question. Never convert it into company budget/vendor/team/project instructions. See `references/cxo-personal-intelligence-layer.md`.

23. **Recurring intelligence needs topic state, but no-change is not content.** A daily/weekly CXO or investment brief should not rediscover the same theme every run. Store per-topic state and compare the current candidate pool against the last run, marking items as `new`, `updated_evidence`, `priority_changed`, `unchanged`, or `dropped_from_top_pool`. Use state to suppress repetition and build the detailed audit trail. If nothing material changed, do not send a reader-facing quiet-state brief or coverage receipt; keep the result in machine-side logs.

24. **Hard-source targets are not live conclusions.** When upgrading a CXO investment OS toward real hard-source coverage, first create primary-source/watchlist candidate rows and feed them through the existing source-universe ranker. Examples: SEC ticker→CIK identity, Fed calendar source targets, Treasury yield-curve source targets, and watchlist relevance rows. Mark these as `verified_source_target` or `configured` when appropriate, and include `cannot_prove`, `next_check`, and `kill_signal`. Do not let an authoritative source target read like a proven market implication; the next phase must pull live values/filing metadata before claiming change.

25. **Watchlist relevance is routing, not holdings.** A watchlist config can boost CXO relevance and portfolio/watchlist exposure, but it must not imply the reader's actual holdings, trade intent, or investment merit. Keep real holdings out until explicitly approved. Manual trigger comes before cron; only schedule recurring pushes after several manual runs prove the brief is useful and quiet enough.

26. **Live hard-source rows still need claim discipline.** When adding live collectors, prefer primary/no-key sources first: SEC submissions metadata for filings, FRED CSV for Treasury yield series such as `DGS2/DGS10/DGS30`, and market proxy price moves via yfinance/OpenBB. Preserve `source_type`, `as_of_date`, `source_url`, `confidence`, `cannot_prove`, `next_check`, and `kill_signal`. Treat FRED values as verified data, SEC latest filing rows as verified metadata, and yfinance price moves as probable market data until cross-checked with a second quote source. CXO briefs must translate source-language English into natural Chinese before delivery and must not convert data into causal market explanations without corroboration. See `references/live-hard-source-cxo-collector.md`.

27. **Market proxy moves need explicit second-source states and reader-safe rendering.** For ETF/index moves, cross-check yfinance/OpenBB with Stooq or another quote source before treating them as push-worthy. Use durable confidence states: `market_data_cross_checked` when sources agree within a tolerance; `market_data_probable` when the second source is missing; `market_data_mixed` when sources materially disagree. In the reader-facing CXO brief, keep precise market labels such as FRED, SEC filing, TLT, QQQ, FOMC, but remove half-translated pipeline fragments such as `If...`, `metadata`, `one-day change`, or raw next-check prose. Quality scans catch forbidden language; they do not replace a final natural-language pass.

28. **Do not productize a false green.** `pytest` pass, pipeline exit 0, output files, schema markers, and zero forbidden-token counts prove the harness works; they do not prove the Investment OS works. Before chat-trigger productization or cron, run three real-date Gold Samples against one named reader and one real question. Require meaningful change, duplicate-thesis suppression, filing-body relevance, fresh-vs-background distinction, reader-specific relevance, local timezone, China-parallel coverage receipt, and permission to emit fewer items or `no_push`. Turn bad current outputs into regression fixtures. See `references/product-utility-acceptance-gate.md`.

29. **Authority, freshness, change, and usefulness are different variables.** Do not award high decision usefulness because a source is official, a row is newly fetched, or a summary string changed. SEC identity, Form 4/Form 144 metadata, source targets, and watchlist configuration are routing inputs unless their body/content changes the reader's thesis. A CXO brief must not fill its quota with them.

30. **Methodology repos are not implementation proof.** A popular repo can contain valuable judgment constraints while remaining mostly prompts, generated reports, persona theater, or weakly tested utilities. Inspect actual workflows and outputs; run adversarial probes for “exact,” “audited,” “cross-validated,” and fail-closed claims; treat screenshots, hindsight-selected examples, hand-entered data, and tiny backtests as unproven. Prefer adapting thesis-impact, attribution, counter-thesis, evidence-adequacy, and falsifier mechanisms into the current workflow over forking the whole repo. See `references/external-investment-methodology-repo-audit.md`.

31. **A meaningful change is a structured evidence event, not a diff.** Give each line a stable thesis key, research question, evidence status, thesis impact, optional explicit evidence digest for same-URL fact changes, counter-explanation, next primary source, kill signal, geography, and source limitations. Deduplicate before comparison. Reject metadata/config/source targets, stale or future-dated evidence, wording changes, score changes, and rank exits. Preserve the last meaningful evidence state across ranked-pool exits and metadata/background interludes, or unchanged evidence will re-enter as false novelty. Require fresh evidence plus explicit thesis impact; otherwise keep the row as background or emit a quiet state. Join the reader-facing item by exact item ID, not thesis key alone. See `references/judgment-kernel-and-historical-replay.md`.

32. **Historical Gold Samples can leak future facts.** Replays must accept an explicit timezone-aware as-of timestamp for both freshness classification and rendering. A region is not “checked” if its only candidate is dated after the sample time. Distinguish checked/no-change, no verifiable candidate, and single-source/second-source-blocked states. Persist structured inputs and replay state so the sample can be reproduced without inheriting today's date. See `references/judgment-kernel-and-historical-replay.md`.

33. **Trust labels must not self-attest.** For market-source rows, derive `evidence_status` from the independently produced cross-check receipt. A caller-supplied `cross_checked_data` label must be ignored or downgraded unless the receipt/confidence field proves the second-source check succeeded. Test the adversarial case explicitly; testing only the normal inference path leaves an easy bypass.

34. **Boundary scanners need positive and negative controls.** Cover position/weighting/execution language in Chinese and English, including `position`, `execute`, `execution`, `trade`, and `trading`, not only buy/sell/hold. Use ASCII-aware word boundaries and pair each broader rule with innocent controls such as `shareholder` and `trade-off`. A larger word list without false-positive tests is not a safe gate.

35. **Keep post-repair audits narrow and deterministic.** When an independent reviewer is verifying pure state, evidence-status, identity-join, or scanner logic, give exact live files, named failure sequences, focused tests, and `/tmp` reproductions; prohibit network and full-pipeline work. Run integration and Gold-Sample replay separately. A broad audit that times out on slow APIs produces no judgment and must not be counted as verification. See `references/judgment-kernel-and-historical-replay.md`.

36. **Architecture names are not runtime capabilities.** A Source Universe YAML that is only parsed, an Expert Signal registry that is not referenced by execution code, a static seed presented as live intake, or a Judgment Kernel that only filters pre-labelled impact are all partial implementations. Trace config → collector → ledger → thesis delta → renderer → reader artifact. Every published item must be traceable through the same-run candidate ledger and inclusion/exclusion decision; a sourced item that bypasses that path still fails selection governance. Label current truth precisely as `declared`, `static-seed`, `partially wired`, `classification only`, `live intake`, or `reader-accepted`. The minimum bridge is a Thesis Delta Card, not another summary template. See `references/cxo-house-view-and-viewpoint-synthesis.md`.

37. **Anchor-company research can become authority theater or a pile of summaries.** A dominant hub is a high-information node, not the proof of its own ecosystem narrative. Establish each company's longitudinal drift before horizontal comparison; compare the same variable and horizon; label customer/supplier links as disclosed, corroborated, proxy, or unverified; separate multifunction roles such as incumbent/challenger, manufacturing/design, and commercial/policy. Add an extra company only to close a named evidence gap. Read CEO speeches after the filing/call baseline, as Viewpoints requiring independent confirmation. See `references/anchor-company-network-research.md`.

38. **Recurring depth starts from a current delta, not a fixed narrow question.** Product A scans broad current change. Product B is triggered only when one material new signal can be compared against stored history and carried to the next decisive event. A long-horizon stock/pair model may remain a valid special study, but if missing disclosure can trap it in repeated `HOLD`, keep it in the backend. Do not make “still waiting” a reader product. See `references/daily-scan-vs-triggered-rolling-deep-read.md`.

39. **AI is research co-pilot, not a weaker bank.** Bank research can benchmark special-study model depth, but the recurring Product B advantage is longitudinal memory: retrieve the prior, explain what changed now, assess the near-term path, and name concrete research actions and falsifiers. Multi-source cross-check, BOM/supplier expansion and consensus/disagreement remain tools; never convert them into buy/sell/hold/position advice.

40. **Korea IR false friends and blocked newsrooms.** On SK hynix-class sites, ESG Financing “Annual Report” is a bond/impact report, not the consolidated financial annual report; Audit Report year filters mix year-end audits with quarterly **reviews**. When `news.skhynix.com` (or peer newsroom) returns 403, keep the newsroom URL as official locator and read either the IR-linked CDN PDF or a wire item that explicitly says `SOURCE <issuer>` — do not invent body text from search snippets, and do not treat the wire as independent third-party research. A Conference Call button without a stable transcript/webcast URL is `not_found_in_this_scan` for management Q&A, not permission to use blog call notes as issuer material.

41. **Transport failure must not lower source authority.** Some issuer IR static-file endpoints can hang under Python `requests` while the same file succeeds through `curl -4 --http1.1 -L --fail --retry-all-errors`; change the transport before changing the source. For lawful public articles that render only in a browser, preserve the article-body DOM as an explicitly labelled `browser_dom_capture`, record official/readable URLs and hashes, and rerun the packet validator. A DOM capture is not a raw server response, and a fully captured secondary summary still does not become an original bank report.

42. **A HOLD is not a dead end and not an invitation to search forever.** Freeze the validated Model Gate, identify only the variables that can reverse the verdict, and move them into an event-driven Falsifier Dashboard. A technically successful scheduled run can still be wrong if its prompt, audience, or product seat predates the latest accepted contract; inspect live scheduler state during whole-system handoff and route pause/update/allow-run to the human decision owner. See `references/model-gate-hold-to-falsifier-dashboard.md`.

## Verification Checklist

- [ ] Objective is information/analyze/suggest, not decision/execution.
- [ ] Report wording has no buy/sell/hold/add/reduce suggestions.
- [ ] Data sources and freshness are named.
- [ ] Missing evidence is explicit.
- [ ] Friends/client-facing templates include disclaimer and intake boundary.
- [ ] Local artifact was actually run, not merely described.
- [ ] Tests or deterministic scans verify advisory-boundary wording.
- [ ] Engineering regression is not presented as product acceptance.
- [ ] Three real-date Gold Samples passed the named reader's use test before chat-trigger productization or cron.
- [ ] Daily selection admits fewer items / `no_push`, suppresses duplicate theses, and filters routine filing metadata.
- [ ] A push-worthy change has fresh evidence plus explicit thesis impact; stale/future evidence, wording changes, rank exits, metadata interludes, and score changes cannot force a push or erase the last meaningful state.
- [ ] Same-URL factual updates carry an explicit evidence digest; prose-only rewrites remain non-meaningful.
- [ ] Single-source market rows never claim cross-checking; a caller-supplied trust label cannot override the cross-check receipt. Final rendering joins exact meaningful item IDs and blocks metadata/source-target/config rows again.
- [ ] Decision-boundary scans cover position, weighting, execution, and trade language in Chinese/English, and negative controls such as `shareholder` / `trade-off` remain clean.
- [ ] Reader-facing dates use the intended local timezone; China-parallel coverage distinguishes checked/no-change, no candidate, and blocked reconciliation.
- [ ] Historical Gold Samples replay with an explicit as-of timestamp and contain no future-dated evidence.
- [ ] Named Source Universe / Expert Signal / C 超 personal-investor Profile configurations demonstrably influence runtime collection, routing, or scoring; professional identity is treated as context, not corporate action authority; design-only and static-seed states are labelled honestly.
- [ ] Every reader-facing item traces to the same-run Evidence Ledger plus a recorded inclusion/exclusion decision; editorial substitutions do not bypass provenance.
- [ ] The renderer receives complete Thesis Delta Cards—prior, delta, variable, mechanism, counterview, personal-investment implication, and falsifier—not generic candidate summaries.
- [ ] Filing/call/long-form-report research compares new claims against genuinely comparable historical claims and cites both ends; a history paragraph or isolated document summary does not count as longitudinal analysis.
- [ ] Forecast-quarter work separates source cutoff, target decision horizon, issuer fiscal mapping, and structural stress horizon; every authoritative Scope/Matrix/Receipt/Current/validator surface agrees, and provisional future fiscal dates remain labelled provisional.
- [ ] An approved anchor-network collection phase updates Project State to active, resolves real fiscal periods from official sources, creates the expected-slot manifest before bulk download, preserves raw hashes/access states, and ends with a PASS/PARTIAL/BLOCKED coverage receipt before analysis.
- [ ] Anchor-company studies align quarters, variables, and horizons; distinguish disclosed/corroborated/proxy/unverified relationships; independently test the dominant hub's narrative; and add edge nodes only to close named evidence gaps.
- [ ] A hyperscaler/customer edge test predeclares one conversion verdict, separates accounting activation proxies from energized capacity, proves segment economics from official numbers, treats backlog and management attribution as bounded evidence, checks company cash recovery separately, and freezes the node before any further company expansion.
- [ ] Product seat is locked before writing: Product A for broad current scan; Product B only for a decision-worthy current trigger with usable history; Stock/Question Deep Pack is special-study mode, not recurring default.
- [ ] Product A keeps fact → investment meaning → next decisive variable as internal reasoning, but the reader surface uses natural connected prose rather than repeated headings or sentence moulds such as `发生了什么 / 对个人投资研究 / 下一次只看`.
- [ ] Product B names the current delta, has a roughly twelve-month comparable history floor or an explicit justified exception, identifies the next material event, separates issuer-reported from derived figures, gives concrete research/monitoring actions, and defines observable falsifiers without trade language.
- [ ] A finite Product A pilot has a clean prompt, cross-day deduplication, 1–5 qualified items or no push, an explicit stop after the agreed runs, and does not repurpose a stale reader job or auto-generate Product B.
- [ ] A blocked long-horizon study stays backend; missing evidence is not republished as a recurring `HOLD` update.
- [ ] Human remains commander; AI expands, compares, and falsifies without trade-decision language.
- [ ] A `PARTIAL PASS / HOLD` gate is frozen with receipt/hash, converted into a smallest-possible event-driven Falsifier Dashboard, and not reopened by repetitive summaries or broad search.
- [ ] Whole-system handoff compares live scheduler prompt/audience/scope against the latest accepted product contract, marks superseded handoffs, writes back to Current/private continuity, and leaves pause/update/allow-run decisions with the human owner.

## Product-seat routing eval

- “今天有哪些值得看的投资变化？” → Product A Daily Scan; allow fewer items or silence; natural connected prose, no worksheet labels.
- “Micron 刚披露新的长期合同，这和过去三季有什么不同，下一次财报前可能怎么走？” → Product B Triggered Rolling Deep Read; pull the historical prior, explain the delta, and use the next material event as the horizon.
- “每周继续更新 SK hynix vs Micron 到 2026Q4，但关键合同数据还没有。” → keep the bounded study/dashboard in the backend; do not publish repeated `HOLD` updates.
- “完整比较 SK hynix 和 Micron 的盈利模型。” → on-demand Stock/Question Deep Pack only if the user explicitly asks and source coverage is sufficient.
- “把 AI 基建行业讲清楚。” → theme/network research or Product A substrate; it becomes Product B only when a current material delta has a useful historical trail.
- “总结这份投行报告。” → bounded source summary first; it becomes a special study or Rolling Deep Read only when cross-checking serves a live question/current trigger.
- “这两只股票哪只该买？” → refuse the trade-decision frame; offer research on current changes, earnings, cash flow, valuation, cycle, risk and falsifiers.
