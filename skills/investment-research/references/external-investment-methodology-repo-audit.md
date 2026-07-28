# External Investment Methodology Repo Audit

Use this reference when an external GitHub repo claims to improve investment judgment through prompts, personas, multi-agent debate, checklists, generated reports, or financial-audit tools.

## Goal

Decide what to **adopt, adapt, or reject** without confusing a persuasive README, fluent report, star count, or self-reported performance with proof that the method or implementation works.

Default stance:

> Borrow judgment constraints, not authority theater. Rebuild weak code. Preserve the evidence/question boundary.

## Audit Sequence

### 1. Establish current remote truth

Inspect the current default branch, commit, activity, license, issues, and repository composition. Fresh-clone the remote. Count prompts/docs, executable code, tests, and CI separately.

Classify the repo before judging it:

- methodology / prompt library;
- executable research system;
- generated-report archive;
- data/tooling package;
- trading/execution product.

A prompt-heavy repo can still contain valuable methods, but it is not an implementation base merely because it has many reports.

### 2. Read mechanisms and outputs, not only the README

Inspect:

- the actual workflow/skill definitions;
- representative recent outputs, including strong and weak cases;
- numeric/audit utilities;
- tests and CI;
- open issues about wrong data, stale sources, or unsupported claims.

Treat README capability and performance claims as self-description until independently verified.

### 3. Extract functions from personas

Translate named-investor or role-play prompts into functional checks:

- business essence;
- moat / replaceability;
- inversion and strongest counter-thesis;
- management promise vs delivery;
- capital-allocation history;
- evidence adequacy and unknowns;
- thesis-impact / drift;
- causal attribution and magnitude matching;
- falsifier / upgrade / downgrade conditions.

Keep the function. Drop simulated quotes, celebrity authority, and cosmetic disagreement unless they improve a real decision.

### 4. Run adversarial micro-probes

Do not trust labels such as “exact,” “audited,” “cross-validated,” or “fail closed.” Exercise them.

Minimum probes:

1. **Exact arithmetic:** test `0.1 + 0.2` and inspect the unformatted internal value.
2. **Missing evidence:** an audit with zero fetched/verified values must fail, not pass.
3. **Conflicting sources:** material disagreement between sources must block release or require explicit resolution.
4. **Test reality:** run the repository test command; “no tests collected” is not a pass.
5. **Claim lineage:** verify that a cited report conclusion is traceable to source/date/body, not only a source name or metadata row.
6. **Performance proof:** reject causal claims based on screenshots, hand-entered histories, hindsight-selected symbols, tiny samples, or unbenchmarked backtests.

### 5. Produce an adoption matrix

For each candidate mechanism, record:

| Mechanism | Evidence in repo | Value to our objective | Boundary risk | Implementation quality | Decision |
|---|---|---|---|---|---|
| Thesis drift | Workflow + examples | High | Low after de-trading | Prompt-level | Adapt |
| Persona debate | Role prompts | Low/medium | False-authority risk | Prompt-level | Reject persona; keep counter-thesis |
| Numeric audit | Code + tests/probes | Depends on probes | False-green risk | Proven/unproven | Rebuild or adopt |

Avoid importing an entire repo when 2–4 mechanisms can be tested inside the existing workflow.

## Investment OS Adaptation Kernel

For an evidence/question-layer brief, every push candidate should answer:

1. What changed, from which source and date?
2. Which existing thesis or research assumption does it affect?
3. Is the thesis **strengthened / unchanged / weakened / insufficient evidence**?
4. What is the strongest counter-explanation or counter-evidence?
5. What would upgrade or downgrade this item?
6. Why is it worth the named reader's next 15 minutes?

If items 2–3 cannot be answered, the candidate is background or routing input, not a top brief item.

Useful mechanisms to test first:

- thesis-impact / drift gate;
- attribution with “true cause unknown” allowed;
- evidence-adequacy vs real-world uncertainty separation;
- primary-source body read and management promise tracking;
- domain-specific bottleneck decomposition after a theme is selected.

Do not import direct buy/sell/hold, price targets, position sizing, execution, or forced item quotas into a research-only system.

## Case Note: `xbtlin/ai-berkshire` (reviewed 2026-07-10)

Remote snapshot reviewed at commit `2bf424c5e55e174b5a08c8ff282c2406bd9ca630`.

Reusable concepts found:

- `thesis-drift`: separates fact, price, and wording changes;
- `news-pulse`: causal attribution across company/regulatory/peer/sentiment lanes and permits “true cause unknown”;
- evidence-richness vs investment-certainty distinction;
- earnings/management promise-vs-delivery review;
- supply-chain bottleneck checks: concentration, expansion time, substitutability, utilization, demand growth, qualification time.

Do not treat the repo as an implementation base without repair:

- repository was overwhelmingly Markdown/report content with little executable code;
- no tests were collected by `pytest` at the reviewed snapshot;
- the “exact” calculator exposed `0.30000000000000004` for `0.1 + 0.2` internally;
- the report audit returned PASS with zero verified values;
- the report audit also returned PASS when two sources differed by 50% and one matched the report;
- self-reported returns and hindsight-oriented scripts did not establish causal proof of the framework.

Conclusion for this case: **adapt the judgment mechanisms; reject persona authority and trading outputs; rebuild numeric/audit code with fail-closed tests.**

## Verification Checklist

- [ ] Current remote, license, commit, and composition inspected.
- [ ] Actual workflows and recent outputs read.
- [ ] README and performance claims labeled self-reported unless independently proven.
- [ ] Numeric/audit claims exercised with adversarial micro-probes.
- [ ] Reusable functions separated from personas and simulated authority.
- [ ] Adopt/adapt/reject matrix tied to the real product objective.
- [ ] Direct trade/execution language excluded from research-only adaptations.
- [ ] Proposed mechanisms are tested in real-date Gold Samples before automation.
