# Anchor-Company Network Research

Use this reference when a sector is organized around a small number of companies whose disclosures expose demand, supply, competition, bottlenecks, and capital allocation across the value chain. It is especially useful for semiconductors, cloud infrastructure, energy equipment, banking, and other networked industries.

## Real job

Do not produce several company summaries side by side. Build a **network-state read**:

```text
anchor-company longitudinal drift
× same-variable cross-company conflict
× upstream/downstream propagation
× later outcome
→ sector thesis delta
```

An anchor is a high-information node, not an authority. Its visibility, incentives, blind spots, and role must be stated before using its claims.

## Necessary scope

Start with the smallest set that can explain the network:

1. **Demand/platform hub** — sees adoption, product roadmap, customer demand, and ecosystem constraints.
2. **Manufacturing/supply hub** — sees capacity, utilization, process, input, and capital commitments.
3. **Direct competitor/substitute** — tests market structure, pricing, and alternative routes.
4. **Structural challenger or policy node** — tests whether a new supply/technology/geography can become commercially credible.

Do not add every plausible company at the start. After the core comparison, add **one edge node** selected by the largest unresolved variable:

- memory/input bottleneck → supplier or component node;
- customer demand/monetization → downstream customer or platform node;
- power/logistics/financing constraint → physical or capital node.

This is not a capability limit. It prevents research volume from outrunning the question.

## Corpus contract

For each core anchor, use the same periods and source classes:

- three consecutive quarterly earnings releases;
- quarterly filing or foreign-issuer equivalent;
- prepared remarks;
- complete earnings-call Q&A;
- investor presentation/management report;
- one structural annual filing for business, segment, accounting, risk, and capital context.

For a Gold Sample, three quarters are enough to test the method. Production memory follows the deeper coverage tiers in `longitudinal-research-memory-system.md`.

### Complete call records

Prefer the company's official transcript. If none exists, preserve the official webcast/audio and create a timestamped local transcript with speaker labels and ASR uncertainty. Use third-party transcripts only with lawful access. Search snippets, media excerpts, and short clips are locator-only; they cannot be assembled into a supposedly complete Q&A.

## Comparison sequence

### 1. Longitudinal first

For each company, compare Quarter N-2 → N-1 → N:

- metrics and guidance;
- wording, confidence, and timetable drift;
- recurring analyst questions;
- quantified versus directional answers;
- evasions and non-answers;
- prior commitments versus outcome.

Do not begin cross-company comparison until the internal drift is clear.

### 2. Horizontal by identical variable

Compare only the same economic variable and horizon. Useful variables include:

- demand/deployment;
- units, ASP, and mix;
- capacity, utilization, yield, lead time;
- CAPEX and prepayments/commitments;
- key inputs/components;
- network, power, logistics, or financing constraints;
- gross margin and FCF;
- customer concentration;
- policy/export controls;
- software/ecosystem control.

Mark `non-comparable` when definitions, time scales, or business models differ. A complete-looking matrix is not worth a false comparison.

### 3. Trace network propagation

For each important claim or event:

```text
claim/event
→ demand node confirmation
→ competitor support/conflict
→ manufacturing/supply confirmation
→ adjacent bottleneck
→ revenue/margin/CAPEX/FCF outcome
```

Label each relationship:

- `disclosed_customer_supplier`;
- `independently_corroborated`;
- `industry_proxy`;
- `unverified_relationship`.

Never infer a customer, supplier, order, or revenue exposure merely because a company is rumored to participate in the ecosystem.

## Executive narrative ledger

Public speeches and long interviews from a prominent CEO can reveal narrative drift, timetable changes, and strategic emphasis. They are Viewpoints, not filing facts.

Build the filing/call baseline first. Then record for each important public appearance:

- date and audience/context;
- explicit claim and variable;
- forecast horizon;
- new/repeated/softened/withdrawn status;
- primary source anchor;
- independent confirmation;
- counterview and later outcome.

Prefer complete official video/transcript or a full readable interview. A quote collection is not a narrative ledger.

## Layer maps

If the source uses a metaphor such as a stack, flywheel, or five-layer cake, do not treat the metaphor as fact. Define a provisional working map, state that its taxonomy can be corrected, and attach each claim only to the layer it truly supports.

A useful AI-sector working map is:

1. power and physical infrastructure;
2. semiconductor supply;
3. systems and cloud platforms;
4. models, data, and software infrastructure;
5. applications, workflows, and agents.

A company spanning several layers does not prove all layers are monetizing or scaling together.

## Required outputs

Starter artifact: copy `templates/anchor-network-comparison.md` and adapt the anchor roles, variables, and layer map to the sector.

- company history dossier for each core anchor;
- three-period longitudinal drift table;
- same-variable cross-company matrix;
- network propagation map with relationship evidence states;
- executive narrative ledger when relevant;
- layer-state map when useful;
- Thesis Memory and accepted Thesis Delta Cards;
- ordinary-summary versus anchor-network-read A/B sample.

## Acceptance gate

Pass only when:

- important changes cite both prior and current source anchors;
- the result is not several summaries concatenated;
- at least one real conflict, constraint migration, or shared unknown is identified—or the output honestly states no delta;
- claims from the dominant hub are verified by at least one independent node;
- multifunction companies have their roles separated rather than collapsed into a slogan;
- removing famous names does not collapse the House View;
- at least one result changes the reader's next research question, evidence priority, scenario, budget assumption, vendor question, or monitored variable.

## Failure patterns

- **Hub becomes oracle.** The most influential company supplies both claim and proof.
- **Aspirational equivalence.** A challenger is treated as the incumbent's equivalent before customer, capacity, yield, utilization, and business-model evidence exists.
- **Supplier graph hallucination.** Rumored ecosystem participation becomes a customer/order claim.
- **Speech-first bias.** Keynotes define the research frame before filings and calls establish the baseline.
- **Decorative layer map.** Layers have no claims, variables, evidence states, or falsifiers.
- **Scope by curiosity.** Additional companies are added without closing a named evidence gap.
- **Period mismatch.** Different quarters, fiscal calendars, or forecast horizons are compared as if aligned.
