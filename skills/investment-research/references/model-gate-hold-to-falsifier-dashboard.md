# From Model-Gate HOLD to a Living Falsifier System

Use this when a Product B stock/pair/question study has completed a bounded model gate but cannot earn a Deep Pack or valuation-framework promotion because attribution, contract coverage, segment economics, or cash conversion remains unproven.

## Core judgment

`PARTIAL PASS / HOLD` is a completed research result. It is neither permission to polish the note into a stronger conclusion nor a reason to keep searching without boundary.

The next asset should preserve what would change the judgment:

```text
frozen model + receipt
→ falsifier dashboard
→ event-triggered evidence refresh
→ same-model rerun
→ research-gate brief or Deep Pack promotion decision
```

## 1. Freeze before monitoring

- Lock source cutoff, target horizon, issuer fiscal mapping, model version, scenario definitions, validation output, and artifact hashes.
- Record exactly which mechanics passed and which attribution/evidence gates failed.
- Keep `mechanics`, `evidence`, `company comparison`, and `valuation promotion` as separate verdicts.
- Do not change the model merely because a new article appears. Reopen only when a predeclared variable changes.

## 2. Build the smallest Falsifier Dashboard

Keep only variables capable of reversing the current verdict. Each row should contain:

```text
variable
current bounded value / state
source and source class
what remains unproven
flip threshold or decision condition
next authoritative source
expected event / disclosure window
status: waiting / changed / insufficient / falsified / promoted
updated_at
```

Typical variable classes:

- target-quarter price level and rate of change;
- protected revenue / earnings share and contract terms;
- realized backlog, RPO, deposit, or supply-agreement conversion;
- product-mix economics, yield, and opportunity cost;
- CapEx-after FCF buffer under the same stress;
- issuer fiscal-quarter mapping and target-quarter guidance;
- same-date consensus / old estimate / company-guidance delta.

Do not keep a variable just because it is interesting. If it cannot alter the model, comparison, or next research decision, leave it outside the dashboard.

## 3. Refresh on events, not anxiety

Valid triggers include:

- issuer earnings, filing, guidance, or investor-day disclosure;
- primary contract / pricing / backlog / RPO update;
- credible same-horizon consensus or lawful original bank model;
- industry price or capacity publication that gives a target-period number;
- realized revenue, margin, CapEx, or FCF conversion that crosses a predeclared threshold.

Invalid triggers include:

- another summary repeating the same thesis;
- a new target price with no visible assumption chain;
- broad TAM growth with no company or target-quarter bridge;
- social attention, management adjectives, or price action alone.

When a valid trigger fires, update only the affected inputs, rerun the same validator, compare verdict deltas, update receipt/hash/state, and close or keep the gate. Do not quietly rebuild the model around the new answer.

## 4. Reader product while Deep Pack is blocked

A blocked Deep Pack can still produce a useful **Research Gate Brief** if the uncertainty itself changes research behavior.

The brief should answer:

1. What the market story currently assumes.
2. What the model can already prove mechanically.
3. What attribution or cash bridge is still missing.
4. Why that gap blocks the stronger valuation or company conclusion.
5. Which next disclosure would change the read.

Keep it short and conclusion-led. Do not add target price, trade action, or synthetic conviction. If the gap does not change a real research decision, publish nothing.

## 5. Minimal implementation contract

When the HOLD becomes a living local + reader asset, keep the implementation thin and versioned:

1. **Freeze the base.** Preserve the accepted note, summary, validation and receipt hashes. The dashboard must not rewrite them.
2. **Use one canonical state table.** CSV or JSON owns the predeclared falsifier rows; every row carries current bounded state, source IDs/classes, what remains unproven, flip condition, next authoritative source, event window, controlled status and `updated_at`.
3. **Render, then validate.** A deterministic renderer produces the operator Markdown. A validator asserts the exact variable set, controlled statuses, source-ID resolution, frozen-base hashes, reader markers, and no decision-language or local-scaffolding leakage.
4. **Make the reader product from the same frozen evidence.** The Research Gate Brief should state the earned uncertainty and next decisive disclosures. It must not bypass the dashboard into a stronger company, valuation or trade conclusion.
5. **Version trigger reruns.** A valid event updates only the affected row and creates a dated copy of the model rerun. Never overwrite the frozen base merely because new evidence arrived.
6. **Stop at reader value.** After user-identity cloud creation and content readback, compare the brief with the existing reader product before runtime, automation or a new cron. Engineering green is not permission to automate.
7. **Close state in order.** Final renderer/validator/test run → artifact hashes → cloud create/readback → receipt → owning project/state readback. If a timestamp-writing validator is rerun after hashing, its hash and receipt are stale and must be refreshed before closeout.

A useful initial state is usually every row at `waiting`: this proves the system knows what would change the judgment without pretending a new event occurred.

## 6. Handoff and runtime control

For a whole-system handoff, distinguish project truth from runtime truth:

- Project Current owns the accepted product state and pending decisions.
- The handoff references Current and marks older handoffs superseded.
- Live cron/scheduler state must be read from the scheduler, not copied from an old status note.
- Compare scheduled prompt/audience/scope with the latest accepted product contract. A stale scheduled prompt is a decision risk even when the last run was technically successful.
- Surface pause / update / allow-run as a human decision when the schedule or audience change has commitment cost; do not silently modify it.
- After writing the handoff, read it back, verify referenced paths and upstream validators, write the handoff link back to the owning project/state surface, and verify the writeback.

## Common traps

- Treating HOLD as unfinished work and searching until something agrees.
- Letting a mechanical stress-test PASS masquerade as protected-earnings attribution.
- Treating product mix or HBM mix as automatic consolidated-margin uplift without yield, price, wafer opportunity cost, and group bridge.
- Changing the fiscal-quarter mapping after the conclusion rather than before the model.
- Shipping a full Deep Pack because the source packet is large.
- Leaving a legacy scheduled prompt active after the reader/product contract changed.
