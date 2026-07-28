# Korea / KRX Issuer IR Earnings Corpus Reconnaissance

Use when Product B or Anchor Network needs an official-first source pack for a **Korean-listed semiconductor / memory issuer** (worked example: SK hynix / 000660). Companion to `issuer-ir-sec-earnings-corpus-recon.md` (US SEC 8-K / 10-Q path). This is source reconnaissance only — not company analysis or trade advice.

## Freeze first

1. As-of date/timezone (example session: 2026-07-14).
2. Target fiscal windows only (example: FY2025 + 1Q26).
3. Required slots before download:
   - earnings press release (newsroom + any lawful issuer-distributed mirror);
   - IR earnings release / presentation PDF;
   - conference call / management material (transcript, webcast, or explicit absence);
   - annual report **or** audited consolidated financial statements (not ESG bond reports);
   - product milestone materials when the research question names a technology (e.g. HBM4).

## SK hynix official surface map (class pattern)

| Surface | Path / host | What it is | Common trap |
|---|---|---|---|
| Earnings Release hub | `https://www.skhynix.com/ir/UI-FR-IR06/` | Latest + year filter for earnings PDFs, press links, call buttons | Call buttons may be `javascript:void(0)` — entry ≠ transcript |
| Financial Statements | `https://www.skhynix.com/ir/UI-FR-IR07/` | Interactive charts / Euroland-style tables | Not a substitute for audited PDF pack |
| IR Materials – Audit Report | `https://www.skhynix.com/ir/UI-FR-IR12_T4/` | Year filter: Consolidated / Non-consolidated annual + 1Q / semi / 3Q **Review** | Review ≠ year-end audit opinion |
| IR Materials – Presentation / Event | `UI-FR-IR12_T*` Presentation / Event Materials | Corporate value-up, tech seminar, etc. | Older event decks are not current earnings |
| ESG Financing | `https://www.skhynix.com/ir/UI-FR-IR13/` | Green / SLB frameworks and **ESG “Annual Report”** PDFs | **Not** K-IFRS financial annual report |
| Newsroom | `https://news.skhynix.com/...` | Issuer press | May return **403** to bots; keep as `official_url` even when unreadable |
| IR CDN PDFs | `https://mis-prod-koce-homepage-cdn-01-blob-ep.azureedge.net/web/attach/*.pdf` | Direct earnings / audit PDFs linked from IR UI | Prefer hash + `pdftotext` of the CDN file |

## Official URL vs readable URL (Korea-specific)

Keep both fields always:

- **`official_url`**: issuer newsroom or IR page that establishes authority.
- **`readable_url`**: the file/page actually fully read.

When `news.skhynix.com` is **403**:

1. Do **not** invent newsroom body from search snippets.
2. Prefer the IR-hosted PDF on the official CDN if the IR Earnings Release page links it.
3. A **PR Newswire** (or similar wire) item with explicit **`SOURCE SK hynix Inc.`** is an **issuer-distributed press release**, not a third-party analyst summary. Label access as original issuer text via wire distribution; still keep the newsroom URL as official locator.
4. Never bypass login, CAPTCHA, or paywall.

## Access / read states (use literally)

- `official_IR_page_read; HTTP_200; CDN_PDF_extracted`
- `newsroom_HTTP_403; wire_SOURCE_issuer_full_text_read`
- `newsroom_HTTP_403; IR_PDF_only_read`
- `call_entry_visible; independent_transcript_not_found_in_this_scan`
- `audit_portal_year_filter_read; consolidated_PDF_extracted` / `review_report_extracted`
- `esg_annual_report_located; not_financial_annual_report`
- `snippet_only` / `blocked` / `not_found_in_this_scan`

Search snippets are **locators only**. Do not write snippet numbers as verified facts.

## Preliminary earnings vs review vs audit

Korean issuer materials often stack three layers — keep them separate:

| Layer | Typical artifact | Proves | Does not prove |
|---|---|---|---|
| Preliminary earnings PR + IR deck | Newsroom/PR + `FY20xx Earnings` IR PDF | Company-stated K-IFRS consolidated headline figures for that period; management narrative; product mix charts | Final audited numbers; full notes; HBM absolute revenue split |
| Independent auditors’ **review** | Condensed interim FS + review report (e.g. KPMG Samjong) | Review conclusion under K-IFRS 1034; often cites prior year-end audit opinion in “Other Matters” | Full year-end audit; word-for-word management call Q&A |
| Year-end **audit** | Consolidated / non-consolidated audit report on IR Audit portal | Unqualified (or qualified) audit opinion on annual FS | Product leadership claims; peer comparison |

If the IR deck says “Review of the FY… financial results has not been finalized,” treat headline PR/IR figures as **preliminary** until the matching review/audit package is read.

## Conference call / management material

1. Record the IR Earnings Release entry (title + scheduled KST time) when visible.
2. If the call control is a hidden button / `javascript:void(0)` and no PDF/transcript/webcast URL is exposed, mark `independent_transcript_not_found_in_this_scan`.
3. Do **not** promote third-party call notes (SiliconAnalysts, Seeking Alpha, blogs) into issuer management material.
4. Prepared IR PDF is **not** a full Q&A transcript.

## HBM / product-tech slot (when the research question names it)

Collect separately from earnings:

- Issuer product milestone PR (development complete / sample / mass-production readiness).
- HBM language **inside** the matching earnings IR PDF and earnings PR.
- Optional: later generation (HBM4E) or event showcases — only if in scope.

Boundaries:

- Product PR proves **company claims** on I/O, bandwidth, power, process, readiness timing.
- Earnings materials prove **financial narrative** (e.g. HBM revenue more than doubled YoY; ramp “in line with agreed schedule”).
- Neither alone proves share, ASP, unit shipments, or Micron-relative ranking without additional primary sources.

## Slot-by-slot recon output (Product B)

For each required slot return:

```text
accurate title
official URL
readable URL
publish date / fiscal period
access state
fully read? (yes / partial / no)
author-publisher boundary
can support
cannot support
```

End with:

```text
Access blockers:
Document-class traps:
Still missing for analysis:
```

## Worked anchors — SK hynix as-of 2026-07-14 (session recon)

Use as calibration, not as a permanent fact pack without re-check:

| Slot | Official / readable anchors | Read state in session |
|---|---|---|
| 1Q26 earnings PR | Official: `news.skhynix.com/q1-2026-business-results/` (403). Readable: PR Newswire `...-302750959.html`, SOURCE SK hynix, 2026-04-22 | Full wire text |
| 1Q26 IR PDF | IR hub UI-FR-IR06; CDN `.../18333727317328069.pdf` titled `FY2026 Earnings` (2026.04.23) | Full PDF extract |
| 1Q26 call | IR hub Conference Call entry Apr 23, 2026 9:00 AM KST | Entry only; no independent transcript URL |
| FY2025 earnings PR | Official newsroom FY25 page (403). Readable: PR Newswire `...-302672384.html`, 2026-01-28 | Full wire text |
| FY2025/4Q25 IR PDF | CDN `.../116964051831620258.pdf` titled `FY2025 Earnings` (2026.01.29) | Full PDF extract |
| FS / audit | Audit portal UI-FR-IR12_T4: 2025 Consolidated/Non-consolidated + reviews; 2026 1Q Review PDF `.../21471389770071386.pdf` (KPMG review 2026-05-15; cites 2025 year-end audit 2026-03-04) | 1Q26 review full; 2025 consolidated annual PDF list confirmed, full text may still need extract |
| ESG false friend | UI-FR-IR13 “2025 Annual Report” = Green/SLB impact reports | Not financial AR |
| HBM4 | Official newsroom HBM4 development/readiness page (403). Readable PR Newswire `...-302554538.html` (2025-09-11) + HBM language in FY25/1Q26 IR PDFs | Full wire + IR excerpts |

## Verification checklist

- [ ] Fiscal windows frozen before collection.
- [ ] Every slot has official URL + readable URL + access state.
- [ ] Newsroom 403 did not become “source missing” when an issuer-SOURCE wire or IR CDN PDF was fully read.
- [ ] ESG “Annual Report” was not filed as financial annual report.
- [ ] Preliminary earnings vs review vs audit remain separate rows.
- [ ] Call entry without transcript is explicit absence, not filled from blogs.
- [ ] Snippets used only as locators.
- [ ] No paywall/login bypass.
- [ ] HBM product claims not upgraded into audited financial facts.

## Related

- US path: `issuer-ir-sec-earnings-corpus-recon.md`
- NVIDIA-specific IR/SEC quirks: `nvidia-ir-sec-source-recon-pattern.md`
- Collection contract: `anchor-network-source-collection-contract.md`
- Document-level provenance: skill `research-corpus-provenance`
- Public/mirrored research access labels: skill `public-research-source-audit`
