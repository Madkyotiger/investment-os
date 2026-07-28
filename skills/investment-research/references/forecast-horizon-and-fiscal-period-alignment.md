# Forecast Horizon and Fiscal-Period Alignment

## Use this when

A Product B / company-comparison question names or changes a forecast quarter, while the evidence packet has a different source cutoff or the issuers report on different fiscal calendars.

The correction is not cosmetic. It changes the model gate, comparable periods, consensus set, and what can count as proof.

## Keep four clocks separate

1. **Source cutoff / as-of date** — latest information allowed into the packet. A new forecast horizon does not silently move this date.
2. **Target decision horizon** — the quarter or year the model must explain, such as calendar 2026Q4.
3. **Issuer fiscal mapping** — the reported or forecast fiscal period used for each company. Preserve exact issuer dates; do not assume identical quarter labels mean identical windows.
4. **Structural stress horizon** — longer-range TAM, contract, capacity, or supply-demand evidence used only to test the target-horizon assumptions.

Never collapse these into one `period` field.

## Alignment workflow

1. **Lock the target explicitly.** Write `calendar` or `issuer fiscal` beside the quarter. If the user says only `2026Q4`, default to calendar Q4 when context makes that read clear, and surface the interpretation in the receipt.
2. **Map each issuer independently.** Record the nearest company fiscal period that covers the target window. If the future issuer calendar is not yet formally disclosed, label the mapping as expected/provisional and wait for issuer confirmation before asserting exact dates.
3. **Preserve the source cutoff.** Existing historical documents remain valid evidence up to the original cutoff; do not relabel them as later-quarter evidence.
4. **Reframe the model gate.** Move historical and long-range evidence into one of three roles: direct target-quarter input, bridge assumption, or stress-test context.
5. **Update only owner surfaces.** At minimum: Product B scope, reader/matrix question header, coverage receipt, Project Current, private project Current, and deterministic validator. Update a manifest question field only if the schema actually contains one.
6. **Do not rewrite every row to the new quarter.** A 2027–2028 TAM or contract-duration row can remain correctly dated while being labelled as pressure-test context for a 2026Q4 model.
7. **Re-run targeted validation.** Require the target horizon, source cutoff, issuer mappings, HOLD/READY state, and named evidence gaps to agree across all authoritative surfaces.

## Model-gate shape

For a near-term quarter, prefer three scenarios:

- `spot-cycle` — earnings mainly explained by market pricing and operating leverage;
- `partial-contract` — some volume/price visibility, but meaningful spot exposure remains;
- `structurally-covered` — contract coverage and cash conversion support a more durable earnings base.

Carry HBM/product mix, contract coverage, price mechanism, CapEx, working capital, and FCF through a segment-to-group bridge. The goal is not a polished target price. The goal is to learn whether reasonable inputs reverse the P/E scenario.

## Build the gate as a falsifier, not a forecast

A near-term Model Gate should make the conclusion easy to kill. It does not need to impersonate a complete consensus model.

1. **Classify every input cell.** Use `issuer fact`, `professional estimate`, `derived arithmetic`, or `research stress assumption`. A midpoint between a broker estimate and a dated consensus snapshot is arithmetic, not a fresh consensus.
2. **Define protected share before using it.** `protected revenue share` means revenue assumed not to absorb the full spot-price shock because of contractual floors/fixed pricing, negotiated HBM pricing, or another structural mechanism. Do not add HBM share and contract share unless overlap is known. Volume coverage is not automatically revenue coverage; an eventual agreement target is not target-quarter realization.
3. **Run a small explicit shock grid.** A reusable normalized form is:

   ```text
   unprotected_revenue_loss = revenue × (1 − protected_share) × price_shock
   profit_loss = unprotected_revenue_loss × drop_through
   stressed_operating_profit = operating_profit − profit_loss
   stressed_fcf = base_fcf − profit_loss
   ```

   The FCF line is a conservative sensitivity shortcut, not a company cash-flow forecast. Label the omitted tax, working-capital, volume, mix, and CapEx responses. A useful first grid is `20% / 40%` price shock crossed with `70% / 90% / 100%` drop-through.
4. **Expose the binding threshold.** For the simplified FCF gate:

   ```text
   minimum_protected_share_for_nonnegative_fcf
   = max(0, 1 − fcf_margin / (price_shock × drop_through))
   ```

   This often reveals that the real question is not “does the company have LTAs?” but “what share is protected, and how much FCF buffer remains after CapEx?”
5. **Separate mechanics from attribution.** A scenario can pass mechanically while evidence fails to prove the protected share, HBM profit bridge, or target-quarter FCF. Use judgments such as `MECHANICS PASS / ATTRIBUTION HOLD` or `PARTIAL PASS / PAIR HOLD`; do not promote a harness pass into a company-quality or relative-value conclusion.
6. **Reproduce public valuation arithmetic narrowly.** It is acceptable to recalculate a public summary's covered/uncovered P/E sensitivity when the formula is explicit. Keep it labelled as a reproduction of a secondary summary, not the original bank model, current consensus, warranted multiple, target price, or recommendation.
7. **Ship machine artifacts with the note.** Preserve inputs, scenarios, stress rows, threshold rows, valuation reproduction, source supplement, summary JSON, deterministic validator, and a compact receipt. Complete final edits before hashing; verify receipt hashes before Project Current/private-state writeback.
8. **Separate price level from rate of change.** A sequence of slowing quarterly increases can coexist with an exceptionally high price level. If public evidence stops at a prior quarter plus qualitative moderation, do not insert a numeric target-quarter change. A single broker's target-quarter slope is one dated scenario, not a market-wide forecast.
9. **Do not make HBM an automatic margin uplift.** HBM can improve visibility and strategic mix while consuming disproportionate wafer input, carrying higher cost/bit, or earning less per wafer than a specific conventional server-DRAM product. Model company-specific HBM mix, price, yield, cost, trade ratio, and conventional-DRAM opportunity cost when available. If they are unavailable, mark `HBM ECONOMICS HOLD`; do not let a higher group OPM scenario masquerade as an HBM-derived conclusion.
10. **Contracted HBM supply is visibility evidence, not protected-earnings arithmetic.** A disclosed price-and-volume agreement for an entire supply year does not reveal revenue mix, realized price, floor/ceiling mechanics, yield, margin, customer overlap, or target-quarter profit. It can strengthen the evidence class while leaving `protected_share` unquantified.
11. **Merge parallel audits as new evidence, not as automatic truth.** After delegated researchers finish, re-read every shared Scope/Matrix/Receipt/Current file they touched before editing. Reconcile contradictory source-access grades and report vintages, update stale validator markers when a gate moves from `NEXT/HOLD` to `COMPLETE/PARTIAL`, then rerun both the source-packet validator and model validator. A worker's PASS is a lead until the parent reproduces it.

If the target calendar quarter straddles two issuer fiscal periods, the nearest-period model is a **proxy**, not complete target coverage. Name the uncovered tail and the future disclosure that would close it.

## Worked calibration: SK hynix vs Micron

For a **calendar 2026Q4** target:

- SK hynix maps primarily to `4Q26 / FY2026`.
- Micron maps to the nearest issuer fiscal period covering most of calendar Q4; `FY2027 Q1` may be the expected primary mapping, but it may not cover the entire calendar quarter. A calendar-Q4 December tail can extend into `FY2027 Q2`; preserve that spillover instead of calling the target a one-quarter fiscal equivalent.
- When the issuer has disclosed only its fiscal-year rule (for example, a 52/53-week year ending on a stated weekday), a date computed from that rule is a **derived provisional mapping**, not an issuer-published future quarter date. Show both labels and do not upgrade the calculation into issuer guidance.
- 2027–2028 HBM TAM, LTA duration, and supply-demand estimates remain structural stress evidence, not the primary forecast horizon.

This mapping is an evidence boundary, not a claim that the two reporting windows are perfectly identical.

## Failure modes

- Moving the source cutoff when only the forecast horizon changed.
- Treating two issuers' `Q4` labels as calendar-aligned.
- Inventing future quarter-end dates from reporting habit.
- Rewriting long-horizon source rows as if they directly prove the target quarter.
- Updating the scope but leaving the matrix, receipt, Current, or validator on the old horizon.
- Declaring the model ready because the narrative is aligned while consensus, guidance, and segment-to-group inputs are not.

## Minimum receipt

State in one block:

- target horizon;
- source cutoff;
- issuer fiscal mapping and any provisional element;
- role of longer-horizon evidence;
- current gate (`READY / HOLD / REFRAME`);
- exact evidence that could still flip the result.
