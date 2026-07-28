# Issuer IR + SEC Earnings Corpus Reconnaissance

Use when an Anchor Network needs an auditable, official-first source manifest for a public issuer’s latest reported quarters. This is a **source reconnaissance and coverage-receipt pattern**, not company analysis or investment advice. Official IR and regulator material remain the authority; a lawful complete transcript fallback may fill a call-record gap only after the official route is exhausted and its lower provenance stays visible.

## As-of selection

1. Freeze the requested as-of date and timezone.
2. Select the latest three **already reported** complete fiscal quarters. A company announcement that it *will report* Q2 is evidence that Q2 remains out of scope, not an earnings release.
3. Resolve fiscal period ends, filing dates, accession numbers, and primary documents from the issuer SEC submissions feed: `https://data.sec.gov/submissions/CIK##########.json`.
4. Keep the Q4 earnings report date separate from the annual 10-K filing date. Check for a same-period 10-K/A; record it alongside the original 10-K rather than silently overwriting it.

For each accession, inspect `https://www.sec.gov/Archives/edgar/data/<CIK>/<ACCESSION_WITHOUT_DASHES>/index.json`. The filing directory often exposes earnings releases, CFO commentary, presentations, and the filing body even when the IR page is dynamic or bot-protected.

Keep `official_url` and `readable_url` separate. The first establishes authority; the second is the direct official PDF/CDN file, SEC exhibit, or explicitly labelled lawful fallback actually archived. Search snippets, text mirrors, and rendering proxies may reveal direct links, but remain locators rather than evidence.

## Per-quarter official sweep

Start at the issuer’s IR earnings-release HTML page and explicitly enumerate its **Related Documents**. For each quarter locate:

- earnings release;
- Form 8-K and its result-related exhibits;
- Form 10-Q (or the Q4 / annual Form 10-K);
- standalone prepared remarks;
- full Q&A transcript; if unavailable, official webcast/audio fallback;
- earnings / investor presentation;
- official webcast/audio.

Use only issuer IR and SEC. A CloudFront PDF or media-server player may be used only when the verified IR page directly links to it; label it `Company IR-linked PDF` or `Company IR-linked webcast`, not as an independent publisher.

## Critical distinctions

- **Prepared remarks are not a full call transcript.** Download/text-extract the PDF and check for Q&A markers. If no Q&A appears, label it `prepared_remarks_only`.
- **Webcast availability does not prove full-Q&A coverage.** When no official transcript appears, first preserve the official webcast/audio and attempt timestamped local transcription when access allows. If the official replay requires registration, identity submission, login, or another unapproved side effect, do not submit user details. A lawfully accessible complete third-party transcript may be used as the fallback when the governing collection contract permits it: preserve the official event/replay URLs, label `transcript_origin` as lower authority, state why the official recording was not captured, and never call the fallback official. If no complete fallback exists, record `not_found_in_this_scan`, set `transcription_required=yes`, and keep Q&A completeness unproven.
- **“Not found” is bounded.** `not_found_in_this_scan` means the audited official IR release and linked official surfaces did not expose the item. It is not a global nonexistence claim.
- **Search snippets are locators only.** Read the original IR page before asserting a timestamp, document list, or absence.

## Publisher / editor / legal-status audit

Do not flatten document ownership into a single “author” field. For every source, preserve the relevant boundary:

- **IR release / Exhibit 99.1:** issuer is the publisher and claimant; named media/IR contacts are contacts, not independent authors. Read the associated 8-K Item 2.02 and retain whether the exhibit is `furnished` rather than `filed`.
- **Deck / prepared-remarks PDF:** issuer IR is publisher; retain PDF metadata author as metadata only, and identify named speakers separately. A prepared-remarks file must not be called a full transcript merely because it contains management speaking turns.
- **10-K / 10-Q:** issuer is registrant; record signing officers. Record an independent auditor only when the actual report is present—an SEC-filed 10-Q is not automatically audited.
- **IR-linked webcast:** issuer IR is the publisher/linking authority; player/CDN/vendor is a technical host, not a transcript editor or an issuer spokesperson.
- **Third-party transcript:** record displayed byline, publisher, stated data/API/transcription provider, automation or accuracy disclaimer, and access state. A page self-described as “Full Transcript” can establish only that the publisher so labels it; transcript completeness and verbatim accuracy remain unproven unless independently checked against the recording.

For the latest reported quarter, explicitly reconcile the separate 8-K and 10-Q accessions, their filing dates, the period end, the 8-K Exhibit 99.1 filename, and the transcript’s publisher/editor/provider status. Never infer that the result-day 8-K and the following 10-Q are a single filing.

## Useful access states

Use observable descriptions rather than upgrading access into a content claim:

- `original_IR_page_read; HTTP_200`
- `SEC_HTML_HTTP_200; Item_2.02_and_exhibits_parsed`
- `SEC_HTML_HTTP_200; located_not_full_text_reviewed`
- `PDF_downloaded_and_text_extracted; Q&A_boundary_confirmed`
- `PDF_downloaded_and_text_extracted; prepared_remarks_only`
- `web_player_HTTP_200; playback_not_listened`
- `official_replay_registration_gated; no_form_submitted`
- `public_complete_transcript_downloaded; third_party_lower_provenance`
- `not_found_in_this_scan`

For an 8-K, confirm the Item 2.02 language and record result-related Exhibit 99.x descriptions. Preserve SEC filing dates separately from the company IR page’s displayed publish time. Do not invent a filing time or webcast start time.

## Manifest minimum fields

Every source row needs:

```text
company
fiscal period
period end
report date
source class
document type
source title
official URL
readable URL
access/read state
issuer / publisher / document-metadata author / transcript editor-provider
disclosure legal status (for example, 8-K furnished exhibit or SEC-filed report)
publisher/event time
transcription required
cannot_prove / notes
```

A per-period header can carry the first four fields for subordinate rows if inheritance is explicit. For direct HTML/PDF/player sources, `readable URL = official URL` is valid.

## Verification routine

1. Fetch exact SEC filing URLs and confirm HTTP 200.
2. Parse each 8-K for Item 2.02 / exhibits.
3. Download relevant PDFs and text-extract only enough to establish document type and whether a Q&A boundary exists.
4. Verify web-player retrieval, but label it unlistened unless it was actually sampled.
5. For every downloaded artifact, preserve the original bytes, compute SHA-256 after write, validate PDF signatures, and reject archived bot-challenge/security-verification HTML.
6. Reuse one immutable local file when the same artifact serves multiple manifest roles; separate rows may share a local path and hash, but conflicting hashes are a failure.
7. A complete public transcript fallback needs a coarse body check: dedicated transcript container, plausible full length, prepared remarks plus analyst Q&A, and multiple operator/speaker turns. Word count and turn count test completeness, not verbatim accuracy.
8. Reject report dates after the research cutoff and verify every issuer has exactly the intended period slots and source classes.
9. End with a coverage receipt: collected/downloaded/linked/blocked states, fallback provenance, recording/transcription queue, exact anchor readiness, and what cannot yet be proved.

A hash-ready raw corpus is not yet a Claim Ledger. Page, section, timestamp, and speaker-turn anchors may remain the next normalization step if that boundary is explicit.

## AMD + Intel example (as-of 2026-07-13 CST)

The cross-issuer trial established these reusable outcomes:

- AMD FY2026 Q1 / FY2025 Q4 / FY2025 Q3 each exposed a full official transcript and Q&A boundary on the IR-linked PDF; no standalone prepared-remarks item was listed.
- Intel FY2026 Q1 / FY2025 Q4 / FY2025 Q3 each exposed prepared remarks, presentation, and official audio, but the audited Related Documents did not expose a standalone complete official Q&A transcript. The official replay required personal-information registration, so no form was submitted. Three complete public transcripts were preserved as explicitly lower-provenance fallbacks after transcript-body and operator-turn checks; the official IR/replay links remain the provenance anchors. If an official-audio-derived transcript becomes mandatory, these calls return to the transcription queue.
- AMD FY2025 had both a 10-K and same-day 10-K/A; a source corpus needs both accessions and must not imply their amendment differences without comparison.
