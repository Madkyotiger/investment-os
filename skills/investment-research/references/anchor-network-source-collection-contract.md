# Anchor-Network Source Collection Contract

Use this reference after an anchor-company pilot has been approved and the next session must build the source corpus. The job is **collection state**, not premature analysis.

## Phase transition

An explicit instruction such as “换个 session 开始收集信息” moves the approved collection workstream from `PENDING APPROVAL` to `ACTIVE`. It does not authorize adjacent changes to cron, automation, source subscriptions, budget, execution, or company scope.

Before ending the current session:

1. write a durable handoff;
2. update Local/private knowledge base Current to the same active state;
3. name the exact first action;
4. preserve remaining approval boundaries.

## Real job

Build a source corpus that is:

- official-first;
- period-aligned without false fiscal-quarter equivalence;
- access-labelled;
- immutable at the raw layer;
- hashable and replayable;
- honest about blocked, missing, partial, and transcription states.

Do not begin with a sector-news search, company summary, House View, or “key takeaways.”

## Manifest before download

Create the expected-slot source manifest before bulk collection. Resolve each anchor's latest completed reporting periods from official IR/regulatory sources rather than assuming the same fiscal labels.

Minimum manifest fields:

```text
company
network_role
period_slot
fiscal_period
period_end
report_date
source_class
document_type
source_title
official_url
readable_url
access_state
read_state
language
transcript_origin
asr_state
local_path
sha256
publisher_time
underlying_event_time
as_of_time
source_anchor_ready
collection_status
cannot_prove
notes
```

Recommended controlled `collection_status` values:

- `expected`
- `downloaded`
- `linked_official`
- `blocked`
- `not_found_in_this_scan`
- `needs_transcription`
- `needs_review`

`not_found_in_this_scan` is a scan result, not proof that a source or event does not exist.

## Corpus contract

For each core anchor and each selected quarter, check:

1. earnings release;
2. quarterly filing or foreign-issuer equivalent;
3. prepared remarks;
4. complete earnings-call Q&A;
5. investor presentation or management report;
6. official webcast/audio;
7. source date, fiscal period, event date, publisher time, and underlying event time;
8. source URL, access/read state, local file, hash, and anchor readiness.

Add one structural annual filing per company.

## Source priority

1. Company Investor Relations.
2. Regulator/filing source.
3. Company official webcast, audio, presentation, or management report.
4. Lawfully accessible complete transcript.
5. Professional media only as a locator for omitted events.

Never assemble media quotes, search snippets, or short clips into a supposedly complete call record.

### Complete call fallback

- Prefer the official transcript.
- If absent, preserve official webcast/audio and create a timestamped local transcript with speaker labels and ASR uncertainty.
- Use third-party transcripts only with lawful access.
- Keep audio/transcript provenance explicit.

## Storage contract

```text
research-memory/
  source-manifests/
  raw/<company>/<annual-or-period>/
  normalized/
  receipts/
```

Raw files are immutable. Do not rewrite PDFs, HTML, audio, or transcripts for formatting consistency. Put parsing, normalization, and local transcription under `normalized/`.

## Tranche sequence

### Tranche 0 — expected-slot manifest

- Resolve periods for every core anchor.
- Record fiscal-calendar and period-alignment differences.
- Build the full expected-slot manifest.
- Do not bulk-download yet.

### Tranche 1 — representative demand + manufacturing anchors

Collect one demand/platform hub and one manufacturing/supply hub first. Verify naming, storage, hashes, time fields, transcript handling, and receipt shape.

### Tranche 2 — competitor + challenger/policy anchors

Copy the verified contract. Express issuer differences through fields and notes rather than redesigning the schema midstream.

### Tranche 3 — coverage receipt

Report expected/downloaded/linked/blocked/not-found states, source-class gaps, transcription needs, period-alignment issues, and the condition for starting Company Dossiers.

A session may end `PARTIAL` after any tranche. Partial collection must not be relabelled complete.

## Collection-session boundary

Unless explicitly expanded, the collection session must not:

- produce a House View;
- add edge companies before a named evidence gap appears;
- start executive speech/narrative analysis before filing/call baselines;
- infer customer, supplier, order, or revenue relationships;
- bypass paywalls, DRM, login, or redistribution restrictions;
- modify cron, source automation, or the existing reader product;
- produce buy/sell/hold, position, target-price, or execution advice.

## Completion receipt

```text
STATUS: PASS / PARTIAL / BLOCKED
Manifest: path + row count
Official source slots: expected / downloaded / linked / blocked / not_found
Companies complete: list
Companies partial: list + missing source classes
Transcription needed: list
Period alignment: pass / gaps
Boundary scan: pass / issue
Current updated: yes / no
Next move: exact tranche
```

## New-session start contract

A collection handoff should end with one executable instruction that says:

- which Current and handoff files to read;
- that system redesign is out of scope;
- that the manifest comes before download;
- the tranche order;
- required source/access/hash/time fields;
- forbidden adjacent work;
- required receipt and Current writeback.
