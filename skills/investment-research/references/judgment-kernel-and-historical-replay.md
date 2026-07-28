# Judgment Kernel and Reproducible Gold-Sample Replay

Use this after the product-utility gate proves that source ranking and summary-string diffs still generate false positives.

## Structured research-question card

Every candidate should carry, at minimum:

- `thesis_key`: stable research-question identity used for deduplication;
- `research_question`: the hypothesis or unknown being tested;
- `thesis_impact`: `strengthened`, `weakened`, `unknown_narrowed`, `unknown_expanded`, `unchanged`, or `unknown`;
- `evidence_digest`: optional explicit version/hash of the source facts, used when a live page or filing URL can change in place without URL/date churn;
- `evidence_status`: primary body read, primary data, cross-checked data, single-source data, metadata only, source target, config only, or unknown;
- `counter_explanation`: strongest plausible alternative explanation;
- `next_primary_source`: the next source that can decide the question;
- `kill_signal`: evidence that downgrades the line;
- `geography`, source URL, source date, and what the source cannot prove.

A high score, official source, new fetch, or rewritten summary is not a meaningful change by itself.

## Change-gate order

Apply gates in this order:

1. Deduplicate candidates by `thesis_key`; choose the best evidence representative, not the highest prose score.
2. Reject metadata-only, source-target-only, config-only, stale, and future-dated rows.
3. Compare evidence identity: source, URL, source date, evidence status, confidence/limitations, next primary source, structured thesis impact, and any explicit `evidence_digest`. Exclude free-form summary wording from the fingerprint so prose cleanup does not create novelty.
4. If the evidence identity did not change, classify summary changes as `wording_only` and score/rank exits as `ranking_only`. If a same-URL page genuinely changes, the producer must change `evidence_digest`; a changed structured impact is itself a judgment change.
5. A push-worthy result requires fresh evidence plus explicit thesis impact. Use reader-facing labels such as hypothesis strengthened/weakened or key unknown narrowed/expanded.
6. Permit an explicit quiet state when no candidate passes.

State retention is part of the gate, not storage housekeeping. When a thesis drops out of the ranked pool, retain its last evidence fingerprint as inactive state; when metadata, source-target, stale background, or evidence-without-impact appears between meaningful observations, do not overwrite the last meaningful evidence state. Otherwise unchanged evidence can re-enter later as a false `new_question` or repeated hypothesis update.

Routine Form 4/Form 144 metadata should stay `metadata_only` until the body/content changes a real research question. Duplicate FRED/Treasury rate lanes should collapse into one stable macro thesis.

## Evidence-status and rendering integrity

- A market source type is not proof of cross-checking. Default yfinance/OpenBB/market proxy rows to `single_source_data`; upgrade only when an independently produced reconciliation receipt such as `confidence=market_data_cross_checked` confirms a second source. For market-source types, derive `evidence_status` from that receipt and ignore/downgrade a caller-supplied `cross_checked_data` label; trust status must not self-attest.
- Join Topic Change to the reader-facing candidate by exact `item_id`, not thesis key alone. A metadata row that shares a thesis with a meaningful filing-body row must not borrow its gate.
- Defensively block `primary_metadata_only`, `source_target_only`, and `config_only` again before rendering, even if upstream state is malformed.
- User-facing summaries must come from the actual candidate evidence. Never infer a Micron/Vertiv/issuer fact merely because an item ID contains a theme name.
- Reuse the project-wide decision-boundary vocabulary in the final-output scanner. Include Chinese position language and English `position`, `overweight`, `underweight`, `execute`, `execution`, `trade`, `trading`, and position-sizing expressions. Use ASCII-aware boundaries and add negative controls so `hold` does not match `shareholder` and `trade` does not match `trade-off`.

## Coverage receipt semantics

Keep these states distinct:

- `checked, meaningful change found`;
- `checked, no change strong enough`;
- `no verifiable candidate available`;
- `single-source candidate exists, second-source reconciliation blocked`.

Do not say a region was checked using data dated after the sample's as-of time. A missing China candidate is an honest gap, not permission to reuse tomorrow's data.

## Historical replay

Gold Samples must be reproducible later:

- pass an explicit timezone-aware `generated_at` / as-of timestamp into freshness classification and rendering;
- render the sample date from that timestamp, not the current runtime date;
- reject rows with source dates after the as-of timestamp;
- persist the structured input candidates and source packet alongside generated state and brief;
- when replaying sequential thesis drift, use one state file across stages and a separate fresh replay state for each clean run.

Without this, a historical sample can silently become stale, inherit current dates, or leak future information.

## Post-repair audit discipline

Separate logic audit from integration verification:

- first run the focused regression files and tiny `/tmp` reproductions for each named blocker;
- give the reviewer the exact live files and failure sequence, not a broad repo-tour brief;
- prohibit network and the full data pipeline when the audit target is pure state/gate/scanner logic; slow APIs can consume the audit window and return no judgment;
- run the full suite, real pipeline, and Gold-Sample replay as the implementation owner's independent integration receipt;
- do not move from `no-ship` to manual product-value review until the reviewer returns an explicit blocker-by-blocker PASS.

## Primary-source reconciliation

When two official documents show different numbers, first compare definitions and deduction stages before labeling a conflict. Example pattern:

- filing A: net proceeds after underwriting discounts but before offering expenses;
- filing B: net proceeds after underwriting discounts and offering expenses.

The difference may be the disclosed expense bridge, not source disagreement. Record the arithmetic and the source wording.

## Regression fixtures

At minimum test:

- identical rerun → `unchanged`;
- summary rewrite with identical evidence → `wording_only`;
- Form 4 metadata → no push;
- duplicate rate sources → one thesis;
- rank exit → one non-meaningful ranking event; identical re-entry → `unchanged`, not `new_question`;
- metadata/background interlude → does not erase the last meaningful evidence fingerprint;
- same URL/date + changed structured impact → meaningful judgment change;
- same URL/date + changed explicit `evidence_digest` → meaningful evidence update;
- same URL/date + prose-only rewrite → `wording_only`;
- single-source market row → never `cross_checked_data`; caller-supplied `cross_checked_data` without a successful second-source receipt → forced back to `single_source_data`; explicit successful receipt → may upgrade;
- meaningful filing body and metadata sharing one thesis → renderer selects the exact body item only;
- forbidden position/execution language (`position`, `execute`, `execution`, `trade`, `trading`, sizing/weighting variants) → final scan fails, while `shareholder` and `trade-off` remain negative controls;
- theme-shaped item ID with weak evidence → no hard-coded issuer/annual-report claim;
- stale evidence with a manually set impact label → no push;
- future-dated row in historical replay → no push;
- fresh filing-body evidence with explicit impact → meaningful change;
- next-session counterevidence → hypothesis weakened;
- zero meaningful items → quiet brief with honest US/China coverage receipt;
- local sample date preserved during replay.
