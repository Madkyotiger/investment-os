---
name: investment-research
description: "Routes and executes evidence-first investment research across quick market questions, Daily Scan, cross-market wrap, A-share institutional observation, triggered deep reads, named issuer studies, source audits, and reusable research systems. Use for source-backed market research, watchlists, filings, data pipelines, evidence ledgers, longitudinal analysis, portfolio-risk review, or reader briefs. Do NOT use for buy/sell/hold calls, position sizing, target prices, brokerage execution, return promises, or regulated investment advice."
version: 2.3.0
author: Hermes Agent
license: MIT
compatibility: hermes
metadata:
  hermes:
    tags: [investment-research, finance, data-pipeline, advisory-boundary, portfolio-risk, multi-market]
    related_skills: [github-operations, software-development-lifecycle, current-state-docs, financial-content-benchmarking]
---

# Investment Research

## Overview

Build and operate reusable investment-information systems that collect, verify, compare, and explain market evidence without pretending to be a licensed adviser or an automatic trading brain.

The skill has two jobs:

1. choose the right research mode and reader surface for the actual demand;
2. enforce source, freshness, inference, privacy, and no-advice boundaries while doing the work.

It is not a generic report generator. A short current question, a Daily Scan, a source audit, a triggered deep read, and a data-pipeline repair are different jobs and must not collapse into one template.

## Route Gate

Use when the user asks to:

- explain a current market, macro, company, sector, filing, or watchlist change from sources;
- run a Daily Scan, cross-market wrap, A-share institutional observation, deep read, issuer comparison, or evidence audit;
- build or debug a reusable investment data/research workflow;
- produce a reader brief, forwardable note, evidence ledger, or technical receipt;
- evaluate investment-data or research repositories as capability modules.

Do **not** use to choose securities for the user, recommend buy/sell/hold, set position size, give target prices, connect brokerage execution, promise returns, or disguise advice as a score. Reframe those requests into comparative evidence, risks, assumptions, falsifiers, and research actions while leaving the decision with the user.

Pure financial-news editorial benchmarking belongs to `financial-content-benchmarking`. Generic repository operations belong to `github-operations`; implementation follows `software-development-lifecycle`, and reproducible failures follow `systematic-debugging` when available.

## Universal Invariants

1. **Research, not decision.** Allowed actions include opening a primary source, updating a watchlist, checking exposure, revisiting an assumption, monitoring a variable, setting an evidence trigger, or ignoring noise. They never become trade instructions.
2. **Goal before method.** Name the user, decision context, market scope, time horizon, freshness requirement, and success criterion before choosing a provider, model, framework, or output length. Ask only when ambiguity changes the route; otherwise proceed.
3. **Facts before judgment.** Separate reported facts, deterministic calculations, interpretation, assumptions, unknowns, and unsupported claims. Keep original values and derived figures visibly distinct.
4. **Source authority.** Original regulator, exchange, issuer, filing, or official release beats summaries. A faithful readable copy may support reading when the original is blocked, but a search result, title, snippet, social post, or locator is not evidence by itself.
5. **Freshness is a gate.** Exact-interval work needs an explicit as-of or interval, event time when known, publication time, access state, and source strength. Never convert “not found in this scan” into “no event occurred.”
6. **Multi-market by design.** A-share coverage is additive, not the product boundary. Preserve independent source routes for Hong Kong, United States, China, and every other market in scope. Never send HK/US symbols through an A-share adapter or remove one market path because another was added.
7. **Fail closed on bad data.** A successful process is not a usable observation. State requested, present, missing, stale, partial, no-event, source-error, and not-applicable coverage explicitly. Do not invent direction, amount, confidence, or reconciliation.
8. **Private and external surfaces differ.** A client/friend-facing output contains no private holdings, local paths, internal repo names, system labels, or unreviewed conclusions.
9. **No capability theater.** External repos, multi-agent personas, optimizer outputs, and polished reports are capability modules or question generators, not authority. Real source access and reproducible evidence decide.

## Demand Router

Choose one primary route. If the request carries several needs, preserve the reader's decision path: deliver the primary surface first and attach a separate audit or engineer receipt only when it changes trust or action. Do not merge reader prose and system logs into one artifact.

| Route | Default surface | Use when | Output default |
|---|---|---|---|
| `quick-answer` | `reader-chat` | A bounded current fact, mechanism, or “what matters now?” question | Useful conclusion first; exact as-of; essential evidence, uncertainty, and original links or supplied source IDs; normally one phone screen. |
| `daily-scan` | `reader-brief` | Broad current browsing across a defined universe | Zero to four qualified changes; no quota filling; one worthwhile research action; silence is valid. |
| `cross-market-wrap` | `reader-brief` | A/H/US or another multi-market comparison | Organize around cross-market mechanisms, not parallel news dumps; same-day co-movement is not causal proof; call a shared driver only when exposure and transmission evidence support it. |
| `a-share-institutional` | `reader-plus-audit` | A-share watchlist or institutional-observation signals | Reader brief first; ledger, coverage matrix, and source receipt remain available as the Audit surface. |
| `triggered-deep-read` | `reader-deep-read` | A current event materially changes a tracked question | Current delta → historical prior → changed mechanism → path to next material event → falsifier and research action. |
| `named-deep-pack` | `research-pack` | An explicitly requested stock, pair, sector, or bounded question earns deeper work | Confirm source sufficiency; align periods/definitions; show model and evidence gaps; do not make it the recurring default. |
| `source-audit` | `evidence-ledger` | The user asks whether a claim or source is supportable | Claim-level verdict; original source and field semantics; fact/calculation/inference split; evidence strength and gaps. |
| `system-build` | `engineer-receipt` | A reusable research pipeline, data model, collector, or agent workflow must be built | Implement and exercise the smallest coherent system; return tests, artifacts, and remaining gaps—not a mock reader report. |
| `system-debug` | `engineer-receipt` | A connector, endpoint, parser, schema, freshness gate, or run fails | Reproduce, diagnose, repair narrowly, execute again, and report the verified result. |
| `boundary-refusal` | `refuse-and-reroute` | The user asks for a trade decision, position, target, return promise, or execution | Refuse categorically; never imply that more or better data would authorize the agent to choose; offer evidence comparison or research questions instead. |
| `blocked-source` | `evidence-gap` | A decision-relevant source cannot be read or a required fact remains unavailable | Name the exact access/evidence gap, try an allowed authoritative/readable route, and bound the conclusion. |
| `client-safe` | `forwardable-brief` | Existing research must become safe to share with a friend, client, or external reader | Remove private/system residue; preserve facts and caveats; run `anti-ai-writing` final-language QA for formal output. |

### Audience and multi-need rules

- **Personal reader:** watchlist or exposure relevance may be used when the user supplied it; never infer hidden holdings.
- **Friend/client/external:** use `client-safe` as an output overlay after the research route; preserve no-advice language and source limits.
- **Engineer/operator:** prefer `engineer-receipt`; keep market interpretation out unless the failure changes evidence quality.
- **“完整 / full”:** raise the evidence and verification bar. Do not dump every log, path, source row, or hidden worksheet into chat.
- **Reader + audit:** publish the brief first. Put detailed evidence in a separate artifact or compact receipt.
- **Several markets:** use market-specific sources, then synthesize only mechanisms that really connect them. Missing one market is a coverage gap, not permission to substitute another.

For detailed reader style, source-universe selection, and two-tier delivery, load `references/investment-output-style-and-source-universe.md`.

## Output Contract

### Reader surface

- First useful line: judgment, current state, or decision-relevant change—not process narration.
- Default length: one phone screen unless the decision genuinely needs more.
- Keep facts, interpretation, and unknowns legible without turning the prose into a worksheet.
- Cite only sources that carry the conclusion. Preserve original URLs where possible. If the user supplies an unlinked packet, cite its source IDs when available; otherwise label the material unverified rather than presenting it as sourced current fact.
- Natural Chinese or the user's requested language; technical market terms may remain English when they are the normal term.
- No internal filenames, paths, commands, adapter names, evidence-row counts, schema labels, or QA scaffolding.

### Audit surface

Use only when requested, when the evidence is consequential, or when a reader needs to inspect trust. It may contain:

- source/claim ledger and original/readable URLs;
- coverage, freshness, field semantics, calculations, and reconciliation status;
- pipeline/test result, source receipt, and exact remaining gaps;
- files or IDs needed for handoff.

The Audit surface does not replace the reader product. For A-share institutional observation, deliver the brief first, then the audit artifact or a compact receipt.

### Mode-specific minimums

- `quick-answer`: conclusion, as-of, 1–3 decisive facts, uncertainty, and traceable source links or supplied source IDs.
- `daily-scan`: zero to four changes; what deserves attention; one research/monitoring action. No repeated-theme quota.
- `cross-market-wrap`: candidate mechanism, market-specific confirmation or contradiction, explicit non-causality for same-day co-movement, coverage boundary, next variable. When exposure and transmission evidence are missing, use “candidate mechanism,” “possible mapping,” or “co-movement”; do not describe the event as driving, catalyzing, causing, or leading the market move.
- `a-share-institutional`: observed signal, why it may matter, inference limit, next confirmation; audit stays optional.
- `triggered-deep-read`: genuinely new delta, prior state, next-event path, observable falsifier.
- `named-deep-pack`: bounded question, reconciled baseline, scenario/model limits, unanswered variables.
- `source-audit`: claim verdict, authoritative evidence, derivation/inference status, missing proof.
- `system-build` / `system-debug`: verified artifact or repair, commands/tests, exact failure or residual risk.
- `boundary-refusal`: refusal based on authority boundary, never on missing data; more evidence can improve comparison but cannot delegate the trade decision to the agent.

Formal, reusable, or forwardable prose gets `anti-ai-writing` QA after facts and structure are locked. Never add vividness, certainty, examples, or claims that the evidence did not earn.

## Evidence and Source Gate

### Current-intelligence gate

For an exact interval:

1. resolve the timezone and freshness cutoff;
2. search the broad universe before narrowing to a theme;
3. open the original source or a faithful readable route;
4. record publication time and underlying event time where known;
5. deduplicate by event, not headline;
6. separate `included`, `excluded`, `not found in this scan`, `blocked-source`, and `source-error` states;
7. stop or narrow the claim when decision-relevant evidence cannot be read.

A source audit should retain title, publisher, timestamp, original URL, readable URL if different, access state, evidence strength, and inclusion/exclusion reason. Locator-only results stay locators.

### Market routes

- **US/HK recurring market layer:** configured watchlist prices may use yfinance; Stooq is a second-source check only when a live probe returns usable same-date rows. Use SEC/FRED, issuer IR, HKEX, regulators, and original releases as authority for consequential claims.
- **Optional global depth:** OpenBB only when it routes to a genuinely independent provider; FinanceToolkit for normalized statements/ratios when earned; edgartools for complex filing parsing.
- **A-share branch:** AKShare is the keyless adapter; Tushare is optional and credentialed. PBOC/NBS/CNINFO/SSE/SZSE and issuer disclosures remain authoritative. Do not count an absent Tushare token as a gap.
- **Other markets:** add dedicated exchange/regulator/issuer routes as coverage requires. Their absence must be reported as a gap, never as evidence that the market is out of scope.

For A-share operations: route stock, ETF, and index explicitly; never send a stock to an ETF endpoint. Use a bounded Eastmoney → Sina → Tencent stock-history fallback and retain the actual source. Stale data is not usable. `no_event` is not `source_error`. Institutional-flow language is inference, not an observed actor decision. Missing or invalid LHB amounts cannot become net-buy/net-sell direction. Beijing margin data is `not_applicable` when the required exchange route does not exist; do not substitute SSE/SZSE.

## Core Workflow

1. **Frame the real demand.** Identify route, audience, market/source scope, interval or next-event horizon, and failure cost.
2. **Check prerequisites.** Resolve accessible sources, credentials, current project/source authority, and whether the request is reader-facing, audit-facing, or engineering work.
3. **Collect the smallest sufficient evidence packet.** Prefer primary sources; record actual source, time, access, field semantics, and missing coverage.
4. **Reconcile before interpretation.** Align periods, currencies, definitions, issuer calendars, and deterministic calculations. Do not compare unlike numbers because labels look similar.
5. **Form the judgment.** State what changed, why the evidence changes—or does not change—the question, alternatives, and what would prove the read wrong.
6. **Deliver the selected surface.** Reader first by default; audit or engineer receipt separately.
7. **Stress test.** Check source strength, stale/partial data, inference leakage, advice leakage, private residue, market-route errors, and whether the next action stays at the research layer.
8. **Verify and write back.** Run the relevant code/test/readback when there are side effects. Update only the owning project/state/evidence surface; temporary progress stays out of durable knowledge.

For building or adopting a system, load `references/system-build-and-adoption-runbook.md`. For a source-backed runnable mainline, also load `references/source-backed-mainline-spike.md`. For failures, reproduce before changing method and use the live fallback/repair contract rather than inventing success.

## Reference Router

Load only the branch the selected demand needs. Every listed asset is part of the retained capability.

### Reader products and output

- Product A/B/on-demand selection → `references/daily-scan-vs-triggered-rolling-deep-read.md`
- Real Product B execution → `references/triggered-rolling-deep-read-runbook.md`
- Daily versus named deep pack → `references/daily-scan-vs-stock-deep-pack.md`
- Reader style, source universe, two-tier output → `references/investment-output-style-and-source-universe.md`
- Technical green versus reader utility → `references/product-utility-acceptance-gate.md`
- Personal-investor relevance layer → `references/cxo-personal-intelligence-layer.md`
- Current hard-source change tracking → `references/cxo-hard-source-change-tracking-layer.md`
- Live current-source collection → `references/live-hard-source-cxo-collector.md`
- House view / multi-signal synthesis → `references/cxo-house-view-and-viewpoint-synthesis.md`

### Evidence, issuer, and thesis work

- Atomic filing/earnings claims → `references/source-bounded-filing-claim-cards.md`
- Company baseline and capital linkage → `references/company-baseline-reconciliation-and-capital-linkage.md`
- Forecast horizon / fiscal alignment → `references/forecast-horizon-and-fiscal-period-alignment.md`
- Issuer IR/SEC corpus → `references/issuer-ir-sec-earnings-corpus-recon.md`
- NVIDIA IR/SEC worked pattern → `references/nvidia-ir-sec-source-recon-pattern.md`
- Korean/KRX issuer corpus → `references/korea-issuer-ir-earnings-corpus-recon.md`
- Longitudinal research memory → `references/longitudinal-research-memory-system.md`
- Historical replay / judgment kernel → `references/judgment-kernel-and-historical-replay.md`
- HOLD to event-driven falsifier state → `references/model-gate-hold-to-falsifier-dashboard.md`
- Hyperscaler capex to economics → `references/hyperscaler-capex-to-economics-conversion-bridge.md`
- Expert signal as question fuel → `references/expert-signal-crosswalk.md`
- Cross-node thesis delta audit → `references/cross-node-thesis-delta-audit.md`

### Anchor-network research

- Source-collection contract → `references/anchor-network-source-collection-contract.md`
- Network method → `references/anchor-company-network-research.md`
- Reusable assets → `templates/anchor-network-comparison.md`, `templates/company-history-dossier.md`, and `templates/thesis-delta-card.md`

### System design and external capability

- Full build/adoption workflow → `references/system-build-and-adoption-runbook.md`
- Runnable source-backed mainline → `references/source-backed-mainline-spike.md`
- Repository landscape → `references/github-investment-advisor-landscape.md`
- External methodology repo audit → `references/external-investment-methodology-repo-audit.md`
- Historical US/China pilot calibration → `references/us-china-unified-pilot.md`; treat it as a worked branch, not the market boundary.

### Operational depth

- Full failure catalogue and branch verification → `references/operational-pitfalls-and-verification.md`

## Common Pitfalls

- generating one generic “investment report” regardless of the user's demand;
- exposing an engineer receipt to a normal reader, or hiding audit evidence inside polished prose;
- treating a blocked source, missing row, stale price, or optional unconfigured provider as the same failure;
- presenting source count, agent debate, optimizer precision, or report length as quality;
- letting one market adapter become the product boundary;
- turning a research action into a trade instruction;
- making a refusal conditional on missing data, which implies that enough data would authorize the agent to choose a trade;
- repeating a fixed deep question without a current delta;
- calling a technically green pipeline a useful reader product before human evaluation.

Load `references/operational-pitfalls-and-verification.md` for branch-specific traps before material system, source, model, A-share, client-facing, or scheduled-delivery work.

## Done State

Done means:

- the demand route, audience, market scope, time horizon, and output surface are explicit;
- every consequential claim is traceable to opened evidence or labelled calculation/inference;
- freshness, coverage, missing/partial/no-event/source-error states are truthful;
- multi-market routes remain independent and A-share work did not narrow the system;
- reader output is useful without system residue; audit/engineer proof is available when consequence requires it;
- no buy/sell/hold, position, target, return promise, or execution advice leaked;
- code or live writes were actually exercised and read back;
- formal/forwardable prose passed final-language QA;
- the full branch checklist in `references/operational-pitfalls-and-verification.md` was used when the work was material.

## Routing Eval

The executable fixture set is `tests/fixtures/investment_research_routing.yaml`. Representative routes:

- “美债收益率这周发生了什么？只告诉我现在值得知道的。” → `quick-answer` / `reader-chat`.
- “跑今天的投资 Daily Scan。” → `daily-scan` / `reader-brief`.
- “把 A 股、港股和美股放在一起看。” → `cross-market-wrap`; preserve separate market evidence.
- “看这五只 A 股有没有机构行为信号，普通读者版先给我。” → `a-share-institutional`; brief first, audit optional.
- “NVDA 财报后原来的判断哪里变了？” → `triggered-deep-read`.
- “完整比较 Micron 和 SK hynix 的 HBM 兑现路径。” → `named-deep-pack`.
- “核对‘主力资金明显净流入’能不能成立。” → `source-audit`.
- “搭一个可复用的多市场投研管线，并实际跑通。” → `system-build`.
- “AKShare 的 Eastmoney 历史行情突然失败，排查。” → `system-debug`.
- “这五只股票到底买哪只？” → `boundary-refusal`; reroute to evidence comparison.
- “公告打不开，直接说今天没有重要事件。” → `blocked-source`; retrieval failure cannot become a negative fact.
- “改成可以转发给朋友和客户的版本。” → `client-safe`; remove private/system residue and retain evidence limits.
