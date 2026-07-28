# NVIDIA IR + SEC Earnings-Corpus Recon Pattern

Use this as an issuer-specific implementation note under the class-level anchor-network source-collection contract. It records a reproducible official-source route, not an investment interpretation.

## Scope rule

For an as-of collection date, resolve the most recent **three completed and reported** fiscal quarters from NVIDIA official records. Do not assume calendar-quarter labels. Add the latest annual Form 10-K once, even when it is also the Q4 regulatory filing.

## Official-source routing

1. **NVIDIA IR earnings release**
   - Use the IR press-release page as the canonical company URL.
   - Use the corresponding SEC 8-K Exhibit 99.1 HTML as a full-text, official readable counterpart when useful.

2. **Regulatory filings and materials**
   - Retrieve Form 10-Q / 10-K and Form 8-K directly from SEC EDGAR.
   - For NVIDIA earnings 8-Ks, inspect the filing directory / exhibit index. In the FY2026 Q3, FY2026 Q4, and FY2027 Q1 pattern, the filing contained:
     - Exhibit 99.1: earnings release (`q[1|3|4]fy..pr.htm`);
     - Exhibit 99.2: CFO Commentary (`q[1|3|4]fy..cfocommentary.htm`).
   - Do not label the CFO Commentary as a call transcript or spoken prepared remarks unless the source itself says so.

3. **IR event and webcast discovery**
   - NVIDIA IR’s Events & Presentations page is Q4-backed. Its public event service accepts a JSON POST at:

     ```text
     https://investor.nvidia.com/Services/EventService.svc/GetEventList
     ```

     with a body shaped like:

     ```json
     {
       "eventSelection": 0,
       "eventDateFilter": 0,
       "includeFinancialReports": false,
       "includePresentations": false,
       "includePressReleases": false,
       "sortOperator": 1
     }
     ```

   - Filter returned records by the exact earnings-event title. Preserve `Title`, `StartDate`, `EndDate`, `TimeZone`, `LinkToDetailPage`, `WebCastLink`, and `Attachments`.
   - `WebCastLink` is an official NVIDIA-IR-provided destination even if the player is hosted by Q4. Treat it as company-authorized only through that provenance.

## Q&A and media rule

- Prefer an official complete transcript.
- If none is located, record the IR event-detail URL and the IR-provided webcast URL as the fallback source path.
- A webcast landing page that is reachable but asks for registration is **not** readable audio and is **not** evidence that a replay or complete Q&A is available. Record `registration_gated`; do not bypass registration or claim the full Q&A was captured.
- Set `needs_transcription` only as a conditional next step: after lawful access to playable official audio is obtained, produce a timestamped transcript with speaker labels and uncertainty markers.

## Prepared-remarks rule

When the IR event record has no relevant attachment and the SEC 8-K exhibit index only identifies the earnings release and CFO commentary, write:

```text
not_found_in_this_scan
```

for a separately published prepared-remarks document. State that this is a scan result, not proof that no such material exists.

## Time normalization

Keep three clocks distinct:

- issuer release date / reported date;
- SEC `acceptanceDateTime` in UTC;
- event time in the IR record’s stated `TimeZone` (and, if needed, a separately normalized CST/UTC+8 rendering).

Do not infer an exact IR press-release clock from the calendar date alone.

## Manifest statuses illustrated by this route

- earnings release, 8-K, 10-Q/10-K, CFO commentary: `linked_official` or `downloaded` after direct official read;
- separate prepared remarks: `not_found_in_this_scan` when the above scan is negative;
- Q&A/webcast page behind registration: `blocked` or `needs_transcription` only with the explicit access limitation;
- separate investor presentation: do not infer absence from `Attachments=[]`; record it as not located in the selected event record and retain the limitation.
