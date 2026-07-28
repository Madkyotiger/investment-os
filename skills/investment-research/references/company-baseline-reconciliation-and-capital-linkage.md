# Company Baseline Reconciliation and Capital-Linkage Audit

Use this reference after several quarter-level extraction passes have been produced for one issuer and the task is to form one longitudinal company baseline.

## Why this exists

Parallel extraction improves recall but creates a second risk: every worker output can become a competing ledger, with different IDs, paths, granularity, and interpretation. The final system needs one canonical claim/anchor layer and separate audit material.

## Reconciliation sequence

0. **Normalize and index first.** Run the company normalizer before extraction. The resulting index—not remembered reporting calendars or filenames—owns the actual fiscal periods, period slots, file set, source classes, publisher times, transcript provenance, official/readable URLs, and original/normalized hashes.
1. **Preserve worker reports as audit material.** Route all quarter reports into one issuer-level `extractions/<issuer>/` directory. Normalize names by fiscal period. Remove stray copies from generic `reference-md/`, `claims/`, or project-root locations.
2. **Do not bulk-import every card.** Compare worker cards against the existing canonical ledger. Promote only cards that:
   - change the company judgment;
   - add a new failure mode or falsifier;
   - close a real provenance or accounting gap;
   - add a management commitment/non-answer that must be tracked later;
   - materially change the next independent node to inspect.
3. **Generate canonical quotes from source line ranges.** Store anchor specs as `(source path, line start, line end, period, event date, provenance, cannot_prove)`. Build the quote directly from the normalized source rather than copying worker prose. This prevents punctuation/whitespace drift and makes deterministic validation possible.
4. **Keep claim and anchor IDs stable.** Worker IDs remain local to their reports. New canonical IDs follow the project's company/period sequence and point only to canonical SourceAnchors.
5. **Update the dossier only when the promoted claims change the read.** Do not make the main narrative longer merely because the audit pool grew.
6. **Rebuild, then validate.** Verify source hashes, exact line slices, page mapping, claim→anchor references, calculations, cited IDs, provenance labels, no-advice boundaries, canonical extraction paths, and absence of old stray paths.
7. **Recompute artifact hashes last.** Update the receipt only after the ledger, dossier, builder, validator, and extraction routing are final. Then read back Project Current / private project state and append a superseding event rather than rewriting history.

## Filing amendment authority

A later amendment is not merely another corroborating source. It changes the authority of the corrected fields.

1. Preserve original and amended filings, normalized files, locators, and hashes.
2. Mark the original corrected passage as `superseded_filing_text` or the project-equivalent evidence role.
3. Create an amendment anchor for the correction purpose and another for the final corrected wording when they are separate passages.
4. Current claims, dashboards, dossiers, and derived calculations use only the amended values.
5. Original values may appear only inside explicit correction provenance; they must never silently survive in a longitudinal table.
6. The validator asserts both sides: the superseded values are present only in the superseded anchor, and the amended values control the canonical claim.
7. Treat the amendment as field-level unless it explicitly restates broader sections; do not assume unrelated filing facts changed.

## Capital–demand linkage: do not add unlike amounts

Keep these separate even when management discusses them together:

| Field | What it is | What it is not |
|---|---|---|
| inventory | recognized balance-sheet asset | customer backlog or deployed capacity |
| manufacturing / supply / capacity commitments | procurement or capacity obligations, sometimes partly adjustable | guaranteed shipment or revenue |
| cloud-service commitments | issuer's own contracted cloud usage | customer demand |
| investments on balance sheet | capital already invested | customer purchases or circular revenue proof |
| investment commitments | contingent/future capital deployment | completed investment or order |
| land / power / shell guarantees | infrastructure risk support | deployed site, recognized revenue, or certain cash outflow |
| management `total supply` | an aggregate that may include inventory, commitments, and prepaids | an additional independent GAAP pool that can be added to its components |
| inventory / excess-purchase-obligation provisions | realized accounting cost of mismatch | a forecast for every future architecture |
| customer capacity deposits / temporary receipts | customer cash or receivable-offset mechanism under specific capacity terms | firm backlog, non-refundable demand, or full funding of expansion |
| purchase / construction obligations | issuer commitments to equipment, construction, materials, or services | customer orders or recognized liabilities unless the filing says so |
| annual CapEx budget | management's planned capital deployment | committed customer revenue, utilization, or realized return |
| government grants / proposed loans / state aid | conditional public support with jurisdiction-specific terms | cash received, net CapEx, or proof that an overseas fab matches home-market economics |

Rules:

- Never total these into an “order pool” or “demand visibility” number without a disclosed reconciliation.
- For any management aggregate, identify component overlap before comparison.
- Do not net unlike contracts, currencies, accounting states, beneficiaries, or timing buckets merely because they all fund one ecosystem.
- A capital relationship is evidence of linkage, not evidence of circular revenue, uneconomic demand, customer dependence, or customer-funded capacity.
- Trace money flow, purchase flow, pricing, cancellation/contingency terms, overlap, and materiality before changing the thesis.

## Product visibility and overlap test

When management gives a revenue or visibility figure for a new CPU, GPU, accelerator, system, or architecture:

1. Is it recognized revenue, guidance, visibility, announced deployment, or TAM?
2. Is it standalone, integrated, or already included in another platform total?
3. Is the workload incremental, substitutive, or mixed relative to existing products?
4. Are attach rate, ASP, customer acceptance, deployment, and supply constraints disclosed?
5. Did management answer the overlap/cannibalization question, or merely describe use cases?

If these are unresolved, record the number as a management commitment with an overlap falsifier—not as net-new company revenue.

## Issuer-first fact hierarchy

When the same reported fact appears in several quarterly artifacts, the canonical anchor should follow authority rather than convenience:

1. issuer earnings release / management report / presentation for reported results, mix and formal guidance;
2. regulatory filing for accounting facts, contractual obligations, risk language and annual structure;
3. issuer-published provider-edited transcript for management wording, Q&A, non-answers, estimates and timetables;
4. complete third-party transcript only when no issuer route exists, with its lower provenance explicit.

Do not use a provider-edited transcript as the primary anchor for financial facts simply because its prose is easier to extract. It is not issuer-authored or word-perfect. When a transcript adds a management explanation, keep the issuer fact anchor and transcript attribution separate.

## Definition and denominator audit

Before comparing a metric across quarters or companies, record what it includes and excludes. Terms that often look comparable but are not:

- `HPC` versus `AI accelerator` revenue;
- data-center CPU included versus explicitly excluded;
- advanced packaging revenue versus wafer revenue;
- system supply, customer investment, wafer demand and issuer revenue;
- recognized revenue, guidance, visibility, TAM and announced deployment.

A denominator mismatch is a first-class claim, not a footnote. If one issuer excludes a component that another reports separately, do not add, rank or reconcile the figures until the boundary is explicit.

## Detect plan drift, not adjective drift

Longitudinal work should look for changed operating commitments underneath the language:

- new building assigned to a different node;
- fab count increased or cancelled;
- CapEx range or allocation changed;
- production/ramp date moved;
- capacity-balance horizon extended;
- a formerly withheld quantity or definition appeared;
- the same decisive analyst question remained unanswered.

Do not call stronger confidence language a thesis change by itself. A changed capital plan is more consequential than a louder adjective.

## Receipt and state order

Use this closeout order:

1. finish all promoted anchor/claim, dossier, dashboard, builder and validator edits;
2. rerun deterministic validation;
3. compute artifact hashes only after the last edit;
4. write the receipt;
5. verify the receipt hashes against live files;
6. update Current/private project state and append the new event;
7. read back state and parse event JSONL before reporting completion.

Updating counts or state before this order creates stale receipts and false completion.

## Worked calibration from NVIDIA (2026-07-13)

Three independent quarter extractions contained 98 detailed cards. The canonical baseline retained only ten judgment-changing gaps, expanding from 40 anchors / 44 claims to 51 anchors / 54 claims. The promoted set included:

- issuer cloud and investment commitments;
- infrastructure guarantees;
- realized inventory / purchase-obligation provisions;
- a management aggregate that overlapped existing supply fields;
- a new CPU visibility figure whose incrementality versus GPU demand was not answered;
- a more precise product-ramp timetable paired with explicit uncertainty.

The point is not the issuer-specific numbers. The reusable move is: **keep high-recall extraction outside the canonical layer, then promote only what changes judgment, accountability, or the next verification route.**

## Worked calibration from TSMC (2026-07-13)

A second issuer baseline confirmed the reconciliation pattern and added four reusable checks:

- **Plan drift:** a Q3 statement that new buildings would serve N2 rather than N3 was later superseded by a Q1 plan for three new N3 fabs. This was a changed capital plan, not a tone change.
- **Denominator boundary:** TSMC explicitly excluded data-center CPUs from its AI/HPC calculation because conventional and AI-server CPUs could not be separated. That prevents direct addition to another issuer's standalone CPU visibility.
- **Capital-risk separation:** customer temporary receipts, issuer purchase/construction obligations, annual CapEx and conditional government incentives were preserved as different contracts and currencies; they were not netted or labelled customer-funded capacity.
- **Conversion non-answer:** management cited roughly US$50 billion of customer investment per 1GW AI data center but declined to translate it into TSMC wafer demand or revenue. The system metric remained a management account, not an issuer-revenue bridge.

The source hierarchy also changed the build: reported financial facts were moved from provider-edited transcript anchors to issuer earnings releases and management reports, while transcripts remained the source for Q&A, estimates, timetables and non-answers. The final validator checked hashes, exact line slices, provenance, derived calculations, cross-ledger IDs, open forecast periods, dossier citations, extraction reports and receipt hashes before Current/private knowledge base writeback.

## Worked calibration from AMD (2026-07-13)

The AMD baseline added five reusable checks:

- **Normalizer-owned truth:** the normalized index fixed the real Q3 FY2025 / Q4 FY2025 + annual / Q1 FY2026 source slots and preserved the complete-transcript label without upgrading it to issuer-authored or word-perfect.
- **Amendment authority:** FY2025 Form 10-K/A corrected transposed Client drivers. Unit shipments `+15%` and ASP `+31%` became current truth; the original `+31% / +15%` remained only as `superseded_filing_text` provenance. The validator asserted both passages and the canonical claim values.
- **Segment denominator:** AMD Data Center mixes EPYC, Instinct, networking and other products. Data Center growth therefore proved company-side conversion, not AI-GPU-specific revenue. The Q1 ex-China GPU-growth question was retained as a non-answer rather than filled by inference.
- **Commitment aggregation:** unconditional commitments more than doubled, while leases and guarantees expanded. Because the pool mixed wafer/substrate/components, CSP, software and technology obligations, it was not relabelled silicon supply, customer backlog, TSMC allocation, or customer-funded capacity.
- **Constraint stacking:** wafer/back-end, memory/packaging, components, data-center buildout, power and capital appeared simultaneously. This strengthened a provisional cross-company stacking hypothesis without promoting it to an accepted House View.

The completed baseline kept 132 high-recall extraction cards outside the canonical layer, then selected 66 SourceAnchors and 62 Claim Records. Deterministic checks covered original/normalized hashes, quote slices, claim-to-anchor references, amendment authority, calculations, transcript provenance, cutoff dates, open guidance, advice boundaries, anti-AI output, receipt hashes, and Current/event readback.

## Worked calibration from Intel (2026-07-14)

The Intel baseline closed Wave 1 and added five reusable checks:

- **Role separation is not optional.** Keep CPU/products, Foundry segment manufacturing, external foundry commercialization, and manufacturing-policy / government capital as separate claim families. A rise in Intel Foundry segment revenue does not prove third-party foundry demand.
- **External-versus-segment gate.** FY2025 external foundry revenue was only $307M against $17.826B Foundry segment revenue (1.72%). Across three quarters, disclosed external amounts moved $32M → $222M → $174M while segment revenue rose about 28.4% Q3→Q1. Compile both series and reject any synthesis that substitutes one for the other.
- **Capital-gate evolution, not technology slogans.** The FY2025 10-K framed 14A around a significant external customer; the Q1 2026 10-Q broadened the gate to sufficient committed demand through potential external design wins **and** Intel's own product roadmap. Record both formulations, mark the broader gate as current, and still treat design wins / volumes / pricing / prepayments as open.
- **Policy capital is not commercial proof.** Accelerated CHIPS disbursements, equity issuance to the U.S. government, warrants, escrowed shares, SoftBank $2.0B, and NVIDIA $5.0B equity are capital and governance facts. They do not become wafer orders, external foundry revenue, or customer backlog. When the annual filing says the Q3 accounting conclusion was adjusted after SEC consultation, the annual treatment owns current provenance.
- **Captive manufacturing is not supply-chain independence.** Intel still uses TSMC for tiles or whole products and depends on Taiwan for critical compute die; Q1 10-Q also disclosed Israel Intel 7 continuity risk under the Iran conflict. Keep captive-fab strategy separate from Asian supply-chain exposure.

Compiler discipline that mattered:

1. Normalize and index first; let the Intel index own the 18 unique sources and third-party `full_qna` provenance.
2. Accept heterogeneous worker IDs, then canonicalize to one `INTC-...` claim namespace.
3. After packet PASS, enforce a required-evidence checklist; missing judgment-critical spans forced additional contiguous literal cards before build acceptance.
4. Reject transcript anchors before the first `Operator:` / full-call boundary on Motley Fool pages.
5. Keep high-recall cards (109) available as audit material while the canonical layer stores only the compiled anchors/claims plus the decision-frame dossier.

Final verified shape: 18 sources, 130 SourceAnchors, 109 Claim Records, three extraction packets, dashboard cuts, one dossier, and a receipt written only after the last edit and final validator PASS. Wave 1 company baselines can be complete while network Thesis Delta / House View remains deliberately open.
