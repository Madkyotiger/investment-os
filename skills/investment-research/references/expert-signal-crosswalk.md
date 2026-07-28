# Expert Signal Crosswalk for Investment Research

Use this reference when public expert material from X, newsletters, podcasts, or research blogs should improve a US-first investment research note without becoming disguised investment advice.

## Core rule

Expert signals are **question fuel, not truth**.

A public expert post can sharpen the research frame, especially around AI infrastructure, semiconductor bottlenecks, valuation assumptions, capex / FCF stress, and counterviews. It cannot replace primary evidence: filings, financial statements, market data, source freshness, or auditable reports.

## Default source strength

- `verified`: linked primary / auditable data has been inspected.
- `probable`: credible specialist plus inspectable linked data or multiple independent corroborating sources.
- `weak`: single X post, thread summary, screenshot, or unsupported opinion. This is the default for X.
- `blocked`: paywalled, deleted, login-gated, uncited, or inaccessible.

Never upgrade evidence strength because a post is vivid, popular, confident, or from a favored account.

## Ledger categories

Use these categories when expert signals enter the Evidence Ledger:

- `expert_signal_context`: public expert angle worth checking.
- `expert_counter_signal`: serious counterview against an attractive thesis.
- `expert_signal_gap`: claim that cannot yet be verified with inspectable data.
- `expert_signal_review_question`: question created after comparing expert signal with evidence rows.

Suggested row contract:

```text
symbol: affected ticker, sector proxy, index, or theme:<theme_name>
category: expert_signal_context / expert_counter_signal / expert_signal_gap / expert_signal_review_question
claim: compact statement of the public angle
value: quote or paraphrase, never rewritten as fact
source: X handle + post URL, newsletter URL, or research URL
as_of_date: source date
freshness: public_expert_signal / linked_research_reviewed / unverified_social_signal
status: ok / partial / missing
url: canonical source URL
note: evidence strength, why it matters, and what primary data must verify
```

## Crosswalk format

External reports should use a crosswalk, not an authority citation:

```text
Public expert signal
→ Our evidence support
→ Our evidence conflict / gap
→ Research question
→ Next source to inspect
```

Good wording:

- “Public expert signals raise a question about memory / power / capex / valuation that should be checked against primary data.”
- “This signal is not yet verified by the evidence ledger.”
- “The next source to inspect is supplier filings, capex disclosure, revenue pipeline, technical deployment evidence, or financial metric.”

Bad wording:

- “Serenity says X, so X is true.”
- “Experts are watching this, therefore it is an opportunity.”
- “Follow smart money / 10x / certain opportunity / market is wrong.”

## AI infrastructure / Serenity-style method

When analyzing AI equities or semis, the useful method is bottleneck cartography:

```text
AI demand narrative
→ required physical stack
→ emerging bottleneck
→ component / supplier / capacity node
→ market attention rotation
→ evidence to verify or disprove
```

Question modules:

1. **Stack expansion**
   - model demand → compute → memory → networking / optics → power / cooling → packaging / testing → supplier capacity.
   - Ask where the company sits and whether that position gives pricing power, cost exposure, or narrative adjacency only.

2. **Bottleneck rotation**
   - Markets may rotate attention faster than physical bottlenecks resolve.
   - Ask whether the bottleneck is still binding, easing, replaced by a new bottleneck, or unverified.

3. **Narrative dispute detection**
   - Identify the claim that moved the market, who disputes it, and what primary evidence would settle it.

4. **Upstream component triangulation**
   - Before clean pure-play public companies exist, map upstream component exposure.
   - Require revenue linkage, customer linkage, capacity evidence, and source freshness before external use.

5. **Economics before theme**
   - The important question is who captures economics when the bottleneck tightens.
   - Cross-check margins, capex, FCF, peer financial context, and filing language.

## Priority source lanes

Keep the source list narrow and promoted by quality, not quantity.

- P0 supply-chain / system economics: `@aleabitoreddit` / Serenity, `@SemiAnalysis_`, `@dylan522p`.
- P1 counterview lanes: capex/FCF/credit stress, business/revenue quality, valuation assumptions, macro/cycle context.

Promote a new source only when it repeatedly provides at least one of:

- inspectable data;
- technical specificity;
- real counterview;
- a stronger question than the current ledger already asks.

## External QA additions

External/client-safe outputs should block:

- decision / execution language: buy, sell, hold, position sizing, target return, auto trade;
- hype / social-pump language: `10x`, `10倍`, `20倍`, “韭菜”, “收割”, “跟着机构”, “确定性机会”, “sure thing”, “follow smart money”;
- guru-authority framing: treating one account as final authority.

## Verification checklist

- [ ] Every expert signal has evidence strength.
- [ ] Every signal is tied to support, conflict, or explicit gap.
- [ ] No X post is presented as source fact.
- [ ] No personal exposure, conviction, engagement count, or hype language leaks into the external note.
- [ ] The output gives the reader better questions, not a disguised recommendation.
