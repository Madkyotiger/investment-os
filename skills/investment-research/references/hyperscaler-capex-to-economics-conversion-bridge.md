# Hyperscaler CapEx-to-Economics Conversion Bridge

Use after an anchor-company network review has identified a hyperscaler / customer node as the single highest-value thesis-reversal test. The job is not to collect another company summary. It is to decide whether infrastructure spending has crossed into usable capacity and identifiable economics.

## Decision question

Lock one same-window bridge before collection:

```text
AI CapEx / depreciation
→ accounting activation or disclosed deployment
→ identifiable segment revenue / operating income / margin
→ company cash recovery or an explicit lag
```

Predeclare the primary outcome:

- `BRIDGE STRENGTHENED` — capacity activation / deployment and identifiable segment economics improve in the same three-quarter window.
- `LAG OR DETERIORATION` — CapEx / depreciation rises while activation or segment economics lag or weaken.
- `DISCLOSURE GAP` — issuer disclosure cannot separate usable capacity or monetization well enough to judge.

A secondary mechanism label may sharpen the verdict:

- `ECONOMICS-LED RECOVERY PATH` — segment revenue, operating income and margin improve despite rising depreciation; company cash payback may still lag.
- `DEMAND OUTPACING USABLE CAPACITY` — management and filing evidence show revenue or delivery is capped by current capacity.
- `CAPEX ACCELERATION WITHOUT SUFFICIENT MONETIZATION EVIDENCE` — spending is visible but segment economics are not.

Do not substitute a secondary mechanism for the primary verdict. If economics are already visible, capacity constraint is the mechanism / limit, not evidence that the bridge failed.

## Corpus contract

Use the three latest *reported* quarters as of the cutoff, not filenames or calendar assumptions. Create the expected-slot manifest before bulk download.

Preferred slots per quarter:

- official earnings release;
- 10-Q / 10-K;
- earnings-event 8-K;
- earnings slides;
- complete call transcript and official webcast locator;
- standalone prepared remarks when actually issued;
- edited CEO commentary only as a separate management-commentary class.

Preserve `official_url` and `readable_url` separately. If SEC Archives or an issuer event page is blocked, do not bypass the challenge or claim the body was read. Record the access gap and use an issuer-linked filing/release copy or complete public transcript fallback at lower provenance. A blocked 8-K does not block the bridge when the official release and filing cover the required facts; the receipt must still name the missing body.

Stop at a source-coverage receipt before analysis. Raw files remain immutable and hash-checked; normalization produces derivatives only.

## Evidence chain

### 1. Capital committed

Capture quarterly CapEx, annual guide, server / data-center split when disclosed, non-commenced leases, supply/power commitments, financing, acquisitions, and guarantees. Keep unlike pools non-additive.

### 2. Accounting activation proxy

Use filing balances and accounting rules:

- property and equipment in service;
- assets not yet in service;
- technical infrastructure in service where available;
- depreciation and the issuer's stated trigger for when depreciation commences.

Call these **accounting activation proxies**. They do not prove energized MW, TPU / GPU count, utilization, or production workload readiness.

Useful calculations:

```text
segment margin = segment operating income / segment revenue
not-yet-in-service share = not-yet-in-service / (in-service + not-yet-in-service)
quarter balance drift = current balance - prior-quarter balance
```

Never divide the change in assets-not-yet-in-service or in-service assets by quarterly CapEx and call it a conversion rate. Acquisitions, disposals, classifications, accrued purchases and different asset lives break that inference.

### 3. Disclosed deployment

Use management wording only when it names deployment / server ramp / capacity coming online / TPU / GPU infrastructure. Preserve transcript provenance and attribution. Product demand, backlog or chip narrative alone does not prove deployment.

### 4. Segment economics

Prefer official segment tables for:

- revenue and year-over-year growth;
- operating income;
- calculated operating margin;
- filing explanation of operating-income drivers and technical-infrastructure usage costs.

Management attribution may connect deployment to growth; it cannot turn mixed segment revenue into AI-only revenue. Preserve Workspace, core cloud, security, platform, pricing, mix and acquisition confounders.

### 5. Cash recovery

Compare operating cash flow, quarterly FCF and TTM FCF against the CapEx ramp. Company FCF is not segment payback. A valid result can therefore be:

```text
segment economics improving
+ company cash recovery lagging
= ECONOMICS-LED RECOVERY PATH / COMPANY CASH PAYBACK LAG
```

### 6. Demand and future conversion

Backlog, remaining performance obligations, multi-year contracts and hardware agreements are future conversion evidence, not current revenue or cash. Separate normal cloud agreements from hardware delivery, note revenue-recognition horizons, and preserve guarantees / backstops / excess-capacity risk.

## Judgment rubric

Choose `BRIDGE STRENGTHENED` only when all are true:

1. official segment revenue or operating income improves across the window;
2. margin is reported or reproducibly calculated from official segment numbers;
3. filing/accounting evidence shows some assets are entering service or depreciation is rising under a ready-for-use rule;
4. deployment attribution exists or the report clearly labels its absence;
5. acquisition, segment-mix, backlog, transcript and cash-recovery boundaries remain visible.

Choose `LAG OR DETERIORATION` when CapEx / depreciation rises but segment revenue, operating income, margin, activation proxies or cash recovery worsen without a sufficient offsetting bridge.

Choose `DISCLOSURE GAP` when the issuer does not disclose enough usable-capacity or segment-economics evidence to distinguish spending from monetization. Usage growth, token counts, backlog, TPU announcements and CapEx guidance do not close the bridge by themselves.

## Thesis writeback

A single hyperscaler may strengthen a customer-side thesis only as:

```text
one identifiable customer / hyperscaler economics node
```

It does not prove all hyperscalers, independent customer ROI, project-level payback, merchant-silicon substitution, or the whole sector's House View.

Update each prior thesis with:

- prior read;
- new evidence;
- impact;
- remaining boundary;
- changed research question;
- falsifiers.

Do not add a second edge node in parallel. Freeze the first node, write the receipt, and require a named unresolved variable before expanding the company list.

## Required counter-case

At minimum, test:

- segment growth could come from non-AI products, pricing, mix or efficiency;
- backlog includes future hardware revenue or acquisition effects;
- assets-not-yet-in-service and depreciation are accelerating faster than cash recovery;
- acquisition accounting changes balance-sheet comparability;
- guarantees / backstops create nonperformance and excess-capacity risk;
- management attribution is not independent customer ROI proof.

## Verification and close order

1. finalize source manifest dispositions and raw hashes;
2. normalize/index the downloaded corpus;
3. create a source-collection receipt with access gaps;
4. write the conversion bridge with stable claim IDs and exact local anchors;
5. run a deterministic bridge verifier that checks protected evidence strings, calculations, verdict labels and stale-state language;
6. run Python syntax / manifest checks and advisory-boundary scan;
7. hash final artifacts;
8. create the final receipt;
9. update project Current, private Brain Current and append one valid JSONL event;
10. read back both current surfaces, parse the full event log, verify receipt-hash binding, and scan for stale `ACTIVE / unauthorized / review pending` state.

Do not hash before the last report edit. If the verifier fails on line wrapping, normalize whitespace in the verifier rather than weakening the protected evidence check.

## Minimum artifact packet

```text
research-memory/source-manifests/<wave>-<issuer>-conversion-manifest.csv
research-memory/receipts/<wave>-<issuer>-source-collection-receipt.md
research-memory/comparisons/<date>-<issuer>-conversion-bridge.md
receipts/<date>-<issuer>-conversion-bridge-receipt.md
scripts/update_<issuer>_conversion_manifest.py
scripts/verify_<issuer>_conversion_bridge.py
```

Return the verdict first, then only the decision-changing numbers, the unclosed boundary, receipt path/hash, and the next authorization gate. Logs and path inventories stay in the artifacts.
