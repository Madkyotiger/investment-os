# CXO House View and Viewpoint Synthesis

Use this reference when an investment/CXO brief is readable, current, and source-disciplined but the reader says it lacks depth, edge, or a distinctive point of view. The repair is usually not “more news” or “a stronger model.” It is a missing expectation baseline, judgment step, and memory layer.

## Product definition

A CXO investment brief is a **hypothesis-update system**:

> Find the new facts that should make a senior operator revise a capital-allocation, technology, demand, supply-chain, financing, regulatory, or competitive assumption.

It is not:

- a broad market recap;
- a fixed-quota news list;
- a celebrity-investor quote wall;
- a model's free-form opinion;
- a disguised buy/sell/hold service.

A useful item changes what a CXO asks, budgets, investigates, negotiates, monitors, or stops assuming.

## The common failure pattern

A mature-looking system can still split into two weak halves:

1. **Evidence pipeline** — reliable collector, Evidence Ledger, freshness, source strength, topic state, and policy scanners, but poor reader output.
2. **Editorial agent/cron** — strong model doing fresh web research and natural writing, but starting nearly from zero each run.

Symptoms:

- every item follows `fact → generic implication`;
- “why it matters” could fit many companies or dates;
- fresh articles are mistaken for fresh underlying events;
- several unrelated items are forced into one “market pulse”;
- expert signals are safely stored as questions but never become a judgment;
- sharp headlines outrun the comparison basis;
- more sources create more summary, not more conviction;
- the system does not remember what it believed last week.

Diagnosis: the harness has source truth, but no durable **judgment state**.

## Audit design-to-runtime, not architecture names

Do not accept `Source Universe`, `Expert Signal`, `Judgment Kernel`, `CXO Profile`, or `Evidence Ledger` as operating capabilities merely because the docs, schemas, and YAML files exist. Trace the actual path from source to reader artifact.

Check five seams:

1. **Config → execution** — does runtime use the values to collect, route, score, and render, or merely parse/validate that the file opens?
2. **Registry → live intake** — does an expert/media registry drive current collection and source rotation, or does the runner consume a static seed file?
3. **Kernel → generated judgment** — does the kernel derive a thesis delta from evidence, mechanism, and disagreement, or only filter an upstream `thesis_impact` label?
4. **Ledger → reader selection** — can every published item be traced through the same candidate ledger, inclusion/exclusion decision, and priority comparison? A sourced item outside the ledger is still a provenance and selection-governance failure.
5. **One product → one front door** — are the formal renderer, decision-support report, and editorial cron using the same accepted upstream contract, or are they separate products with different evidence and state?

Useful code-audit probes:

- search for configuration filenames in runtime code, not only tests and docs;
- inspect the collector function after config loading to see which values actually shape candidates;
- identify whether the runner passes a live registry, a generated packet, or a hand-maintained CSV seed;
- read the change classifier to separate **classification** from **inference**;
- compare the exact reader items against the same-run Evidence Ledger and excluded-candidate list;
- read the rendered outputs from every nominal front end, including quiet-state files.

Use honest capability labels in current-state docs: `declared`, `static-seed`, `partially wired`, `live intake`, `classification only`, or `reader-accepted`. Do not let a rich architecture diagram overstate runtime truth.

## Audit the real editions before redesigning

Do not audit only prompts, diagrams, YAML, or passing tests. Read at least two recent complete reader-facing editions plus the run path that produced them.

For each edition, check:

1. **Fresh fact** — what truly changed in the declared interval?
2. **Underlying event time** — did the event happen now, or was an old event merely republished?
3. **Expectation baseline** — what did the market, management, or operator previously assume?
4. **Explanatory gain** — what does the analysis explain beyond “risk/cost/opportunity rises”?
5. **Economic transmission** — who pays, who captures margin, who gains control, and on what timetable?
6. **CXO decision lever** — which budget, vendor, project, scenario, or strategic assumption changes?
7. **Counterview** — what is the strongest plausible alternative explanation?
8. **Falsifier** — what evidence would weaken or reverse the read?
9. **Independence** — if source names were removed, would the system's conclusion still stand?
10. **Statefulness** — does the item update an existing thesis, or rediscover the same theme?

A title can be sharp while the item is shallow. Require a defined comparator, base rate, or expectation delta before accepting a high-voltage claim.

## Two clocks: freshness without amnesia

Keep two time windows separate:

- **Event clock** — the exact interval in which the new fact, disclosure, decision, price move, or official statement occurred.
- **Judgment clock** — the older context needed to interpret it: 30–90 day filings, guidance, consensus, investor letters, price behavior, historical base rates, or prior thesis state.

Rules:

- Old context may support a new judgment; it may not masquerade as a new event.
- A newly published article about an old agreement is a fresh interpretation or estimate, not automatically a fresh company event.
- Preserve `publisher_time`, `underlying_event_time`, `as_of_time`, and `context_window` separately.
- Reader copy should label the true delta: new disclosure, new estimate, new interpretation, new market reaction, or new official action.

## Source roles: add functions, not feeds

More viewpoints help only when each source has a defined job.

### Primary evidence

Examples: filings, earnings releases/calls, regulators, central banks, government statistics, official company statements, audited datasets, market/credit/flow data.

Role: prove the narrow fact.

Limit: primary evidence rarely proves the wider causal story by itself.

### Front-line financial media

Examples: Reuters, Bloomberg, FT, WSJ, CNBC; for China, Caixin, Yicai, CLS and other verified outlets.

Role: detect change, provide scene, identify stakeholders, locate primary sources.

Limit: a fresh report does not make its underlying event fresh.

### Professional analysis and columns

Examples: Breakingviews, FT Unhedged, Bloomberg Opinion/John Authers, Heard on the Street; equivalent high-quality China/macroeconomic commentary where accessible.

Role: expose prevailing narrative, causal framing, and live disagreement.

Limit: editorial authority is not evidence authority.

### Senior investors and research thinkers

Examples: Oaktree/Howard Marks, Michael Mauboussin, Aswath Damodaran, AQR, GMO and other candidates selected for method rather than fame.

Role: provide base rates, capital-cycle logic, valuation assumptions, expectations, and risk regimes.

Limit: use mainly as weekly/monthly frameworks; do not force a daily quote quota.

### Domain specialists and KOLs

Examples: semiconductor, AI infrastructure, energy, enterprise software, logistics, China policy, and regulation specialists.

Role: surface technical bottlenecks, early anomalies, and mechanisms before general media catches up.

Limit: followers, confidence, access, or disclosed positions do not upgrade evidence.

### Market behavior

Examples: relative equity moves, credit spreads, options, rates, commodity curves, flows, and peer reactions.

Role: test what appears priced or surprising.

Limit: price action does not prove causality.

## Viewpoint card

Normalize useful opinions into a card before synthesis:

```text
source / author:
domain and time horizon:
explicit claim:
assumptions required:
evidence cited:
strongest counterview:
observable variable that would support it:
observable variable that would falsify it:
public exposure / incentive boundary, if disclosed:
source role: discovery / consensus / framework / specialist / counterview
confidence and access boundary:
```

Track whether a source repeatedly offers useful, testable variables before expanding its weight. Do not score celebrity.

## The judgment chain

For every candidate thesis:

```text
fresh evidence
→ prior consensus / operating assumption
→ strongest supporting interpretation
→ strongest counterview
→ evidence cross-check
→ economic transmission
→ bounded House View
→ named CXO decision lever
→ falsifier / next decisive check
```

### Thesis Delta Card — the only publishable upstream object

Do not feed a reader-facing renderer with a generic candidate summary. Promote a candidate only after it becomes a Thesis Delta Card:

```text
thesis_id:
prior: what the market / management / system previously assumed
delta: what is genuinely new versus the prior state
underlying_event_time:
publisher_time:
variable: revenue / margin / capex / financing / demand / supply / competition / policy
mechanism: how the fact transmits to the variable
primary_evidence_ids:
supporting_interpretation:
strongest_counterview:
thesis_impact: strengthened / weakened / delayed / unknown narrowed / unknown expanded
CXO decision: named role + budget / vendor / project / scenario / research priority
confidence_boundary:
falsifier:
next_trigger:
US_evidence_status:
China_evidence_status: comparable / divergent / China evidence gap
```

Promotion gate:

```text
fresh fact
+ explicit prior
+ named variable
+ credible mechanism
+ thesis change
+ counterview
+ falsifier
+ CXO decision lever
```

If any critical field is missing, keep the item in the evidence/source-check queue. Do not let good prose rescue an incomplete card.

For US-first + China-parallel work, keep two evidence lanes under the same question card. If China has no comparable first-source material, write `China evidence gap`; never translate the US conclusion into a China claim by analogy.

### House View contract

A House View is not a confident sentence. It contains:

```text
What changed:
What the prevailing read says:
What the prevailing read misses:
Our current read:
Why this read fits the evidence better:
Who pays / captures / controls:
Which CXO assumption changes:
Confidence boundary:
What would weaken or reverse the read:
Next update trigger:
```

The view must still make sense after removing the famous names. If it merely paraphrases one columnist, analyst, investor, or KOL, label it `borrowed_view` and do not publish it as the system's judgment.

## Permanent CXO decision levers

Replace keyword-only relevance with operating levers:

- capital cost and financing;
- capex and return period;
- revenue, demand, and pricing;
- technology adoption and vendor control;
- supply chain, energy, and operating cost;
- policy, geopolitics, and competitive structure.

Optionally tag the most affected role:

- CEO / strategy — strategic options, competitive structure, irreversible bets;
- CFO — financing, capex return, cash flow, risk scenarios;
- COO — supply, logistics, capacity, operating cost;
- CIO/CTO — adoption, architecture, vendor dependence, implementation burden;
- other roles only when the item changes a real decision.

Do not generate five versions by default. Produce one common executive core with one or two role-specific implications.

## Minimum durable state

Before adding more agents, create three small assets:

### Thesis Book

```text
thesis_id
topic
current_house_view
prior_consensus
supporting_evidence_ids
counter_evidence_ids
confidence
last_meaningful_update
falsifier
next_trigger
status: active / weakened / strengthened / overturned / archived
```

### Viewpoint Registry

Store source role, domain, horizon, evidence habits, disclosed incentive boundary, recurring bias, useful calls, misses, and keep/watch/drop status.

### CXO Decision Map

Map event classes and thesis changes to named executive levers, budgets, vendors, projects, scenarios, or questions.

Without these assets, a daily editorial model will rediscover themes and sound generically intelligent.

## Delivery cadence

### Daily Signal Brief

- 2–4 items; one or two are valid on a thin day.
- One lead judgment only if earned.
- Each item compresses: hard fact, current read, CXO implication/question.
- Do not require a detailed document every day.
- No meaningful hypothesis update means no push.

### Weekly Conviction Note

- One main thesis, at most two adjacent judgments.
- Include consensus, counterview, evidence, economic transmission, scenario, and falsifier.
- This is the primary home for senior-investor frameworks and deeper viewpoint collision.

### Monthly Thesis Scoreboard

- strengthened, weakened, overturned, or stale theses;
- sources that supplied useful variables versus sources that only supplied rhetoric;
- repeated themes consuming attention without new evidence;
- dead theses and low-value sources to remove.

## Multi-agent gate

Do not add a Research Committee, bull/bear personas, or debate agents merely because the brief lacks edge.

They are allowed only after:

- a prior-consensus field exists;
- the thesis state is durable;
- evidence and viewpoint roles are distinct;
- the expected output is a bounded House View, not a debate transcript;
- one-agent manual samples already show the judgment chain is useful.

Otherwise multi-agent debate amplifies summary volume and authority theater.

## Acceptance labels for reader review

Ask the named CXO/decision owner to mark each item:

- `changed_the_question` — changes an ask, budget, investigation, negotiation, or monitored variable;
- `correct_but_inert` — factually sound, no decision value;
- `borrowed_view` — a media/investor claim restated in system voice;
- `headline_overreach` — language sharper than comparator/evidence;
- `over_inferred` — causality or confidence exceeds evidence;
- `stale_as_fresh` — old event presented as current change.

A sample passes only when:

- event time and context time are honest;
- every main judgment has a baseline, system read, and falsifier;
- at least one item changes the reader's next question;
- the expert names can be removed without collapsing the conclusion;
- the reader surface is scannable in roughly 15–30 seconds;
- no trade decision or execution language leaks through.

## Minimum repair sequence

1. Freeze automation changes.
2. Audit two or more actual editions and the real run path.
3. Preserve evidence, freshness, and no-advice controls.
4. Manually create two revised samples using the judgment chain.
5. Use a small, role-defined source roster; test whether each source changes the read.
6. Add Thesis Book, Viewpoint Registry, and CXO Decision Map only after the samples work.
7. Encode selection, synthesis, and rendering after reader acceptance.
8. Add agents last, if they improve held-out samples rather than merely producing more text.

## Failure conditions

Stop and repair when:

- a “market thesis” is just editorial glue;
- all selected items confirm one fashionable theme;
- the system cannot state the prior expectation;
- the expert layer ends in a crosswalk or question queue with no synthesis owner;
- a detailed note repeats the short brief with more words;
- sharpness comes from harder adjectives instead of an expectation delta;
- every day requires content despite no meaningful update;
- reader praise is about readability only, while no question or decision changes.
