# Longitudinal Research Memory System

Use this reference when an investment/CXO research system must read filings, earnings calls, long-form research, or current news **against prior material**, rather than summarize each source in isolation.

## Product definition

The system is a **stateful hypothesis-update system**:

> Use live change to trigger research, historical evidence to establish the prior, cross-source comparison to form a bounded House View, and CXO decision context to decide whether the change deserves attention.

The moat is not document volume or summary speed. It is traceable historical judgment, comparable claims, disagreement at the variable level, and outcome calibration.

## Source roles

### Regulatory filings

Examples: 10-K, 10-Q, 8-K, 20-F, 6-K, XBRL company facts.

Role: hard fact and disclosure history.

Method: filing diff, not whole-document summary. Track additions, deletions, changed wording, first/withdrawn quantification, segment/CAPEX/inventory/debt/commitment changes, and routine-template noise.

### Earnings calls and Q&A

Role: management-pressure test.

Separate prepared remarks, analyst questions, CEO/CFO/operator answers, quantification, directional answers, evasions, and non-answers. Compare recurring questions, wording confidence, timelines, guidance, and prior commitments across quarters.

### Sell-side and professional research

Role: expectations, model assumptions, causal mechanisms, and disagreement.

Do not treat ratings or price targets as facts. Extract comparable assumptions such as volume, ASP, utilization, margin, CAPEX, FCF, demand, supply, competitive structure, valuation method, catalyst, risk, and horizon.

Access rule: process only public, lawfully licensed, or user-provided material. Record `public / licensed / user_provided / blocked`; never bypass paywalls, DRM, login, or redistribution restrictions.

### Product B bank-note depth benchmark

When the deliverable is a named-stock or named-question Deep Pack, do not stop at industry mechanism, company summary, or document synthesis. Require a full model chain:

```text
incremental facts
→ explicit assumptions
→ segment revenue model
→ group profit / cash flow
→ old estimate / consensus / company-guidance delta
→ valuation framework
→ risks and falsifiers
```

A strong sell-side note is useful because it makes this chain inspectable. AI should not imitate the prose or borrow the rating/target price. Its advantage is to cross-check the chain across company filings, multiple bank/professional notes, customer/supplier/BOM evidence and later outcomes. Every material forecast assumption should be classified as disclosed fact, analyst inference, explicit model assumption, market consensus, or unresolved gap.

Minimum Deep Pack proof:

- one named stock or at most one tight comparison pair;
- assumptions visible rather than hidden inside conclusions;
- segment-to-group financial bridge;
- old-view / consensus / management-guidance comparison;
- cash-flow and capital-intensity check, not EPS only;
- valuation method audited for changing business mix and peer comparability;
- strongest counter-thesis, sensitivity variables and kill conditions;
- disclosed access / incentive boundary for professional research;
- final personal-investor implication states which research variable changes, not a trade instruction.

Stop when the output could still be replaced by a single bank-note summary, or when thin public summaries are being used to simulate bank-level depth.

### Banks' own filings and calls

Keep separate from their sell-side research. Bank disclosures can reveal lending, credit, provisioning, capital-markets activity, deposits/funding, payments, and client behaviour; their research product supplies industry/company expectations.

### Media, specialists, investors, and social sources

Use for event discovery, prevailing narrative, mechanisms, base rates, and counterviews. They are lenses, not authority votes. Social posts are locators or question fuel until linked evidence is inspected.

## Core architecture

```text
Coverage & Question Map
→ Historical Intelligence Base ↔ Live Signal Radar
→ Source Archive
→ Event / Claim Ledger
→ Thesis Memory / Viewpoint Registry
→ Comparative Reader
→ Thesis Delta Card
→ House View / CXO Decision Map
→ Alert / Daily / Weekly / Deep Research / Scoreboard
→ Outcome and reader calibration
```

Product modules describe the value; runtime must remain split into four non-bypassing planes:

| Plane | Owns | Must not do | Proof object |
|---|---|---|---|
| Control | source definitions, coverage, cadence, access, decision map | create facts or briefs | `SourceDefinition`, `FetchPlan`, `CoveragePlan` |
| Evidence | fetch, archive, version, anchors, claims, conflicts, gaps | form a House View | `FetchReceipt`, `SourceVersion`, `SourceAnchor`, `AtomicClaim` |
| Judgment | prior, comparison, mechanism, counterview, Thesis Delta | equate a new source with a new judgment | `ComparisonSet`, `ComparativeFinding`, `ThesisDeltaCard` |
| Delivery | selection, rendering, policy scan, reader feedback | search or insert material outside accepted cards | `SelectionDecision`, `BriefRun`, `ReaderFeedback` |

The front end may consume only an accepted Thesis Delta Card plus its Selection Decision.

## Minimum durable objects

### Source Artifact

Raw file/URL/audio/transcript/table plus source, version, hash, page/timestamp, publisher time, event time, access state, and full/partial/blocked read state.

### Event

A real-world change, separate from the articles covering it. Multiple articles may describe one event; a new article may contain no new event.

### Claim

An atomic fact, management guidance, analyst assumption, interpretation, forecast, or question, anchored to an exact quote/table/page/timestamp.

Comparable keys should include company/theme, metric/variable, period, forecast horizon, source/author, thesis, geography, and mechanism.

### Thesis Memory

Store prior, current House View, consensus, supporting/counter claims, key variables, open questions, management commitments, disagreement, confidence, falsifier, next trigger, and update history.

### Viewpoint Registry

Store source role, domain, horizon, explicit claim, assumptions, cited evidence, strongest counterview, observable support/falsifier, access/incentive boundary, useful calls, misses, and keep/watch/drop state.

### Thesis Delta Card

The only publishable upstream object:

```text
thesis_id
prior
new evidence delta
publisher time / underlying event time
changed variable
transmission mechanism
primary evidence IDs
supporting interpretation
strongest counterview
thesis impact
US evidence state
China evidence state
CXO role / decision object / horizon
confidence boundary
falsifier
next trigger
```

### Operational receipts and invariants

The research objects are not enough; runtime must also persist:

- `SourceDefinition / FetchPlan`
- `FetchReceipt`: configured / attempted / succeeded / blocked / not_due
- `SourceDocumentVersion / SourceAnchor`
- `ExpectationSnapshot / ComparisonSet`
- `SourceCheckTask`: owner, next source, cadence, close condition
- `SelectionDecision / BriefRun`: accepted/excluded/no_push, exact item, as-of, delivery state

Three invariants:

1. Every reader item traces to `SelectionDecision → Thesis Delta → new and prior SourceAnchors`.
2. The same `as_of time + archive snapshot + thesis state` can be replayed without future-data leakage.
3. US-first work keeps a separate China evidence state; missing Chinese evidence remains a gap rather than becoming an analogy.

## Comparison logic

When a new source arrives:

1. Define the research question before summarizing the source.
2. Extract atomic claims and separate fact, guidance, assumption, interpretation, forecast, and question.
3. Retrieve genuinely comparable historical claims, not merely semantically similar documents.
4. Compare four ways:
   - longitudinal: current versus prior period;
   - horizontal: company versus peer/supplier/customer;
   - viewpoint: sources disagree on which variable or assumption;
   - outcome: prior forecast/commitment versus later fact.
5. Explain economic transmission: who pays, who captures margin, who gains control, and on what horizon.
6. Assemble the strongest plausible counterview.
7. Produce only the delta: unchanged prior, new evidence, strengthened/weakened/overturned assumption, unresolved gap, and next decisive source.
8. Promote only a complete Thesis Delta Card.

A history paragraph is not longitudinal analysis. Prior material must change the comparison, confidence, mechanism, or next question.

## Two clocks for live intake

Preserve separately:

- `publisher_time`: when an article appeared;
- `underlying_event_time`: when the disclosure/decision/change happened;
- `as_of_time`: the research cutoff;
- `context_window`: older material used to interpret the event.

Old context may support a new judgment; it cannot masquerade as a fresh event. Cluster syndication and duplicate reporting before selection.

## Historical coverage tiers

Separate method proof from production memory; do not let a shallow MVP masquerade as a longitudinal system.

- **Gold Sample:** four to eight quarters for core companies plus directly relevant annual filings, calls, and professional research.
- **Production Core:** at least five years / twenty quarters; strong cyclical industries continue to the previous complete supply/capex cycle.
- **Peer:** roughly eight quarters plus several annual filings.
- **Watch:** latest annual, recent quarters, and thesis-relevant events.
- **Emerging:** backfill only after a credible thesis appears.

Production historical assets:

- Industry Memory Pack
- Company History Dossier
- Thesis Memory
- Forecast Accountability Scorecard

Forecast accountability locks the original company guidance, external assumption, or internal forecast with the evidence available at the time, then compares later outcomes. Separate error into direction, magnitude, timing, and mechanism. Never rewrite the original prediction after the fact; mark thin samples unscorable.

A useful initial coverage structure is one shared macro/credit/capital-allocation base plus a small number of industry verticals. Macro is a common scenario and financing layer, not automatically another standalone industry report.

Each priority industry should maintain:

- value chain and profit pools;
- company/peer/supplier/customer map;
- key variables and lead/lag relationships;
- filing diff and call drift;
- management commitment ledger;
- sell-side assumption matrix;
- US/China comparison and non-transfer boundary;
- Thesis Book, evidence/access gaps, and next triggers.

## Storage and retrieval

Start thin:

- filesystem for immutable raw sources and access-separated proprietary files;
- SQLite/DuckDB for artifacts, events, claims, relations, and state;
- FTS5 and deterministic metadata routing first;
- embeddings/vector retrieval only after real corpus scale proves metadata/keyword retrieval insufficient.

Do not add a knowledge graph or multi-agent committee before manual comparison samples prove value.

## Model allocation

- deterministic tools: collection, timestamping, dedupe, diff, table/speaker parsing;
- cost-optimized models: routine claim extraction and initial matching;
- strongest capable model: cross-document comparison, mechanism, counterview, Thesis Delta, and House View;
- final editor: compress to natural CXO language without upgrading evidence strength.

Functional seats are not automatically separate agents. Split Collector/Extractor/Comparator/Analyst/Skeptic/Editor/Publisher only when held-out samples show a quality gain.

## Reader products

- Event Alert: one major delta.
- Daily Signal Brief: two to four publishable deltas; zero means no message; one uses Alert.
- Weekly House View: one main thesis and at most two adjacent judgments.
- Deep Research Note: filing/call/report/industry question with historical comparison.
- Company History Dossier and Industry History Pack: durable research substrate.
- Monthly Thesis Scoreboard: strengthened, weakened, overturned, stale, source usefulness, and attention audit.

Reader output hides ledgers, queues, scan receipts, schemas, and process language. It shows the fact, current read, affected CXO decision, confidence boundary, and next decisive check.

## Migration from a legacy candidate pipeline

Use a strangler migration rather than a rewrite:

- old Evidence Ledger rows become `LegacyObservation`; only rows with recoverable source versions and anchors may upgrade to `AtomicClaim`;
- static expert seeds become weak `ViewpointCard`s;
- SEC identity, source targets, and watchlist config remain routing inputs, not evidence;
- old topic state becomes dedup state, not thesis truth;
- hard-source collectors write Archive/Claim objects instead of publishable candidates;
- delivery switches only after replayable filing, viewpoint-conflict, and US/China-gap samples pass.

## Fail-closed degradation

- Fetch failure: write a receipt; stale versions remain background only.
- Parse failure: preserve artifact/metadata; do not create claims from titles or snippets.
- Paywall/permission gap: keep locator and access boundary; never bypass or redistribute.
- Conflicting first sources: keep both claims as mixed/contested.
- China data gap: state the gap; block judgments that require bilateral comparison.
- Missing prior/mechanism/falsifier: hold the card in draft/needs-verification.
- Renderer/state/policy failure: do not send an old brief as current.
- No meaningful change: `no_push` with machine-side receipts only.

## Minimum proof before implementation

Run one bounded Gold Sample before building the full system:

1. choose one theme and two or three core companies; for a sector whose truth depends on network propagation, use the smallest role-complete anchor spine from `anchor-company-network-research.md` instead of obeying the company count mechanically;
2. backfill four to eight quarters of filings/calls;
3. add a small set of lawfully accessible professional reports;
4. build two Thesis Memories manually;
5. use the same new source for A/B: ordinary summary versus longitudinal comparative read;
6. ask the named reader whether the comparative version changed the next research question.

Proceed only if at least one item is marked `changed_the_question` and every important delta cites both new and prior source locations. Do not invent percentage pass thresholds from a tiny pilot; early proof asks whether the comparison changed a real question, evidence priority, scenario, budget assumption, vendor question, or monitored variable.

## Failure conditions

Stop or repair when:

- the output could be replaced by a single-document summary;
- historical material appears only as background prose;
- retrieved sources share a topic but not the same metric/horizon/mechanism;
- famous names are doing the argumentative work;
- source names can be removed only by collapsing the House View;
- a report rating/price target is treated as fact;
- a new article is mistaken for a new underlying event;
- US evidence is transferred into a China claim without comparable evidence;
- no meaningful change still produces a routine brief;
- access rights are uncertain or redistribution is not permitted;
- system maintenance costs more research time than it saves.
