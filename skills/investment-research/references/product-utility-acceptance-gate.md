# Investment Intelligence Product-Utility Acceptance Gate

Use this when an investment-research pipeline is technically green but the reader-facing brief may still be useless.

## Failure pattern

A pipeline can pass source-schema, file-generation, forbidden-language, path-leakage, and no-trade tests while failing the real job: helping a time-poor reader decide what deserves research attention now.

Typical false-green signals:

- daily output is a fixed pilot theme with only the date refreshed;
- source-universe lanes exist in YAML/tests but not as live collectors;
- generic keyword hits are called personalization;
- source authority is treated as decision usefulness;
- routine SEC metadata such as Form 4 / Form 144 enters top items without reading the filing body;
- two items repeat the same macro thesis;
- summary-string changes are called thesis/evidence changes;
- China-parallel exists only in config/ledger and leaves no coverage receipt;
- language QA catches banned tokens but misses repetition, half-translation, and empty professional prose;
- UTC dates appear in a local-reader brief.

## Separate three test layers

### 1. Engineering regression

Proves collectors, schemas, caches, files, and deterministic boundary scans work. Necessary, never sufficient.

### 2. Product acceptance

A brief passes only when it:

- contains 2–4 meaningful changes from the relevant 24–72 hour window; fewer or silent is allowed;
- changes research-attention allocation, not merely reports available data;
- connects each item to the named reader's real questions, horizon, and exposure without inferring holdings;
- states what changed, why it matters, the next research question/action, and the downgrade/kill condition;
- suppresses duplicate theses;
- distinguishes fresh evidence from stale background and source targets;
- admits when a configured lane was checked but produced no push-worthy change, and distinguishes that from having no verifiable candidate;
- uses the reader's local timezone;
- historical samples use an explicit as-of timestamp and reject evidence dated after it;
- remains inside the no-advice boundary.

### 3. Human use proof

Before chat-trigger productization or cron, run three real-date Gold Samples. For each, ask:

1. Would the intended reader finish it voluntarily?
2. Did it change what they would research next?
3. Which item looked professional but was actually useless?
4. Could it be forwarded or used as a conversation hook without explanation theatre?

Encode only the selection rules that survive these samples.

## Gold Sample workflow

1. Freeze module expansion and renderer polishing.
2. Choose one real reader and one real question.
3. Use existing collectors plus fresh auditable sources to create a manual/semi-manual Gold Sample.
4. Compare it against the automated brief.
5. Turn current bad outputs into regression fixtures: repeated rates, routine SEC metadata, fixed-theme output, missing China coverage, stale source promoted as fresh, future-dated evidence in a historical sample, broken mixed-language prose, wrong local date.
6. Persist the sample's structured inputs, source packet, timezone-aware as-of timestamp, and generated state/brief so it can be replayed later without inheriting current dates or future facts.
7. Only then patch ranking, change detection, personalization, and renderer logic.

## Minimum architecture corrections after proof

- meaningful-change gate;
- filing-form/body relevance filter;
- stale-background vs new-evidence state;
- duplicate-thesis suppression;
- reader-specific question/horizon profile;
- local-timezone handling;
- per-lane coverage receipt;
- explicit `no_push` outcome when nothing deserves attention.

## Decision rule

`tests pass + pipeline exits 0` means the harness works. It does not mean the Investment OS works.
