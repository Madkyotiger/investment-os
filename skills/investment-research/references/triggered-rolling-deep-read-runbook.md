# Triggered Rolling Deep Read｜Execution Runbook

Use this when Product B is being run on a real current event. This is not a fixed company note or a long-horizon forecast template.

## 1. Candidate gate

A candidate enters Product B only when all four are true:

1. **Current delta** — a new filing, earnings result, price/volume move, policy action, contract, operating metric or company decision changes the live question.
2. **History floor** — there is enough comparable history to explain the delta. Prefer four reported quarters / roughly twelve months; if the canonical dossier is shorter, add the missing issuer period before writing.
3. **Next material event** — there is a named near-term event that can advance or falsify the read: earnings, guidance, policy implementation, price reset, contract milestone or another disclosed data point.
4. **Research action** — the reader can do something now at the evidence layer: pre-register variables, update a watchlist, check exposure, open a primary source, or set an event trigger.

If any gate fails, keep the item in Product A or the quiet backend. Do not manufacture a B quota.

## 2. Build the evidence packet

Minimum packet:

- one primary source for the current trigger;
- one primary or verified historical source that closes the twelve-month comparison;
- the latest company guidance / prior judgment;
- a small source manifest separating opened primary evidence, internal verified synthesis and locator-only sources;
- deterministic calculations for every derived number.

Keep reported facts and derived figures visibly separate. A currency conversion using a guidance FX assumption is a comparison, not reported revenue. A quarter derived by subtracting Q1 from first-half revenue must be labelled as calculated.

## 3. Find the judgment shift

Do not repeat the trigger as the thesis. Ask what question the new evidence makes obsolete and what nearer question replaces it.

Useful pattern:

```text
old question: is demand / adoption / policy support real?
current delta: the top-line or operating signal is now established
new question: does it convert into margin, cash, utilization, capital efficiency or another decision variable?
next event: the disclosure that can answer that conversion question
```

The history must change the interpretation, not merely add chronology.

## 4. Reader structure

Lead with the current signal and the changed question. Then:

1. show the twelve-month trajectory on the few comparable variables that matter;
2. explain why this event differs from the prior pattern;
3. give one main path and at most two alternatives through the next event;
4. specify what to inspect at that event;
5. name observable falsifiers.

Depth is earned by a better comparison and a nearer decision, not by length. Avoid visible worksheet language unless the artifact is an internal template.

## 5. Delivery and review

- Keep buy/sell/hold, position, target price and execution advice out of the reader surface.
- Preserve original source links; keep paths, claim IDs, receipts and source counts backstage.
- Run anti-AI-writing before formal delivery.
- For cloud delivery, create under the user-owned folder and read back title, numbers, links, actions and falsifiers.
- Ask for short reader feedback: whether history added value, the piece was too long or too technical, and whether the action became clearer.

## 6. Relationship to Product A pilots

A finite A pilot may run on a schedule when the user explicitly asks for a multi-day test. Its contract should be zero to four qualified items, cross-day deduplication, no quota filling, and an explicit stop after the agreed runs. Keep the legacy job paused; create a clean pilot job rather than repurposing a stale prompt. Product A may surface a B candidate, but it must not auto-publish Product B.
