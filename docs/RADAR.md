# Daily radar

The radar is the path a daily brief actually runs on. An agent does the research with its own search and reading tools; this package gives it the history to start from, checks what it brings back, stores the run, and reports what the runs managed to collect.

The split is deliberate:

- **The agent** finds, opens and reads sources, judges what changed, and writes the brief.
- **The program** verifies that every cited source was really captured, rejects items that break the evidence or advice boundary, remembers earlier judgments and open questions, and refuses to let silence stand in for "nothing happened" when coverage is incomplete.

The program does not fetch sources, write prose, schedule runs, or deliver anything. A hash proves which bytes were saved; it does not prove they are true.

## One run

```bash
# 1. What was said before, which questions are due, what must be covered this round
uv run investment-os radar preflight \
  --config configs/upstream_radar.sample.yaml \
  --runs-root reports/upstream-radar \
  --db reports/upstream-radar/radar-index.sqlite \
  --out reports/upstream-radar/preflight/seen-state.json

# 2. First-hand official captures into the run folder (optional, recommended)
uv run investment-os radar collect \
  --run-dir RUN --config configs/radar_hard_sources.sample.yaml --sec NET,CRWV

# 3. The agent researches and writes RUN/live-packet.json plus RUN/evidence/*

# 4. Validate the packet, select qualifying items, store the run
uv run investment-os radar evaluate \
  --packet RUN/live-packet.json --config configs/upstream_radar.sample.yaml \
  --out RUN/output --run-dir RUN --db reports/upstream-radar/radar-index.sqlite

# 5. After the agent has written and reviewed the final text, attach it and re-validate
uv run investment-os radar evaluate ... --delivery-file RUN/final.md

# Read back the stored state
uv run investment-os radar store readback --db reports/upstream-radar/radar-index.sqlite
```

`preflight` writes the full manifest and a compact `seen-state-digest.json` to read first. A missing or empty database blocks preflight: an empty history must be rebuilt on purpose, not assumed.

`evaluate` exits `0` on `pass` and `1` otherwise. It writes `reader-brief.md` (a worksheet rendering), `selected-items.json`, `run-receipt.json` and `delivery-final.md` under `--out`. The receipt always records `claim_sent: false`: a rendered or stored text is not proof of delivery.

## First-hand captures

`radar collect` fetches the official, machine-readable sources listed in a config and saves each one under `RUN/hard-evidence/` as readable text with its SHA-256. It writes `hard-sources.json` (SourceManifest rows the agent copies into the packet for the captures it cites) and `digest.md` (the latest values in plain lines, plus anything that could not be captured).

| Source | What is captured |
|---|---|
| FRED series | The series CSV: rates, inflation, labor, oil. FRED gives observation dates, not release dates |
| TreasuryDirect | Auction results of the last days: term, high yield or discount rate, bid-to-cover, size |
| Shanghai Futures Exchange | Settlement, change, volume and open interest of the most-traded contract per metal, for the last finished trading day |
| Listed pages | An official page such as the NOAA ENSO discussion, checked against its expected title |
| SEC EDGAR | For each ticker passed with `--sec` (or an SEC CIK number): filings in the lookback window, and for 8-K and 6-K the attached documents, which carry the earnings release |

Rules:

- For HTML and JSON sources the saved body is a text rendering, one table row per line. The raw response is stored beside it when small and always hashed in the manifest.
- A response that is not the requested document is written with `identity_status: mismatch`, which the validator will not accept as evidence.
- A source that could not be fetched is listed under "Not captured". Record it as a gap; it does not mean nothing happened.
- An exchange file published before settlement is not a finished day and is skipped.
- `--strict` exits `1` when anything requested was missing or mismatched.
- SEC requests need `SEC_EDGAR_IDENTITY` (a name and contact email, as SEC asks of automated clients).

The sample list comes from what real daily runs kept citing second-hand or recording as gaps. Sources that refuse plain requests (BLS release pages, LME, USDA at the time of writing) are not on it; the agent still has to read those itself or record the gap.

## Packet

```json
{
  "schema_version": "upstream-radar-packet-v2",
  "as_of": "2026-09-08T07:20:15+08:00",
  "run_id": "2026-09-08-072015",
  "sources": ["<SourceManifest>"],
  "coverage": ["<CoverageRow>"],
  "items": ["<CandidateItem>"],
  "followup_updates": ["<FollowupUpdate>"],
  "delivery_artifact": {"kind": "agent_final", "text": "final text, optional during research"}
}
```

### SourceManifest

| Field | Required | Meaning |
|---|---|---|
| `source_id` | yes | Unique in the packet |
| `url` | yes | URL actually fetched or shown |
| `requested_url`, `captured_title` | for evidence | What was asked for and what came back |
| `kind` | yes | `evidence`, or `locator` (records a discovery, never counts as evidence) |
| `access_completeness` | yes | `full`, `excerpt`, `partial`, `blocked` |
| `identity_status` | for evidence | `match`, `mismatch`, `unverified`: is the returned document the one requested |
| `body_path`, `sha256` | when bytes exist | File under the run directory and its SHA-256 |
| `captured_at` / `accessed_at` | yes | Timezone-aware; verified evidence must be captured within 24 hours before `as_of` |
| `publication_time`, `publication_time_precision` | recommended | When the source was published |
| `observation_period` | optional | Underlying reporting period such as `2Q26`; never used for the freshness window |
| `recovered_source_id` | on mismatch or block | The source that replaced this one |

Only `evidence` with `identity_status=match` and `full` or `excerpt` access, complete capture fields, readable UTF-8 bytes and a matching hash counts as verified. `partial` never passes as a full read. An excerpt can support a bounded claim only when the item's `bounded_quote` appears literally in the saved bytes. `body_path` must stay inside the run directory: no absolute paths, `..`, or symlinks.

### CoverageRow

```json
{"domain": "macro_upstream", "check": "energy_geopolitics", "status": "checked", "source_ids": ["s03"]}
```

`status` is `checked` or `checked_no_change`. The required checks come from the config. A row that only gives a count or a URL list, without `source_ids`, fails.

### CandidateItem

Each item names its `source_id`, a stable `tracking_key`, a `thesis_key`, the fact, `prior_view`, `evidence_delta`, `interpretation`, the transmission path, a falsifier, and either `counterevidence` or `declared_gaps`. `publication_time` anchors the 72-hour freshness window. With `require_opportunity_context: true` an item also states `opportunity_hypothesis`, `affected_companies`, `expectation_gap` and `valuation_context`; "not verified" is an acceptable value, an invented one is not.

Every qualifying item is selected. There is no item quota in either direction.

## Rules the validator applies

- **A gap affects only what depends on it.** A defective source makes that source unusable; items built on it are excluded and the rest are published. The receipt lists every gap. The run is blocked only when nothing qualifies and gaps exist, because silence would then pass for "checked, nothing happened".
- **Open questions are tracked, not forgotten.** Each selected item opens a question under its `tracking_key`. A due question is covered by a `followup_update` backed by sources from this run, or by new selected evidence under the same key. Reviewing is not resolving: an unresolved question stays `open` with a later `next_check_at`. Uncovered due questions are listed in the receipt on a publishing run and block a silent one.
- **Questions expire.** A question whose latest selected evidence is older than 14 days is no longer mandatory; no question lives longer than 45 days. New evidence under the same key restarts the clock.
- **Gaps in the schedule are caught up.** When the last successful run is more than 72 hours old, preflight returns `catchup_since` and the packet must carry it. Items found in the catch-up window are marked as late discoveries.
- **No final text, no publication.** With selected items and a submitted final, the text must be non-empty. If the packet records a `writing_gate`, only `status=pass` with `delivery_authorized=true` unblocks it.
- **No trade instructions.** Buy, sell, hold, position-size, target-price and execution language is rejected in items and in the final text.
- **Silence is explicit.** With `silent_no_push: true`, a run with nothing to publish stores `[SILENT]` as its final. Evidence, candidates and question reviews are still stored.

## Collection report

```bash
uv run investment-os radar collection-report \
  --runs-root reports/upstream-radar --days 7 \
  --config configs/upstream_radar.sample.yaml --out reports/upstream-radar/collection-7d.md
```

The report restates what the runs in the window recorded: status of each run, days without a passing run, each coverage check's results, every source host with usable and unusable counts, gaps recorded by the validator, gaps the researcher declared, and how many due questions went unreviewed. It adds no judgment.

This is the feedback path into this repository. A gap that keeps recurring in real runs (a data series the agent can never read first-hand, a source that is always blocked) is the evidence for adding a collector, changing a source route, or correcting a rule here.

## Weekly live check

Unit tests cannot tell that a source changed its format or started refusing requests. Run the live paths on a schedule and alert only on failure:

```bash
uv run --extra market investment-os daily --config configs/watchlist.sample.yaml \
  --profile configs/profiles.sample.yaml --state /tmp/selfcheck-state.json --out /tmp/selfcheck-daily --strict
uv run --extra china investment-os a-share-daily --config configs/a-share-watchlist.sample.yaml --out /tmp/selfcheck-a-share --strict
uv run investment-os radar collect --run-dir /tmp/selfcheck-radar --config configs/radar_hard_sources.sample.yaml --strict
```

Each command exits non-zero when its path is broken. Pair them with `radar collection-report` over the last week of real runs, so the same review sees both what broke and what the runs could not read.

## What stays outside this repository

Reader lists, delivery channels, schedules, the real source pool and run history belong to the deployment. `configs/upstream_radar.sample.yaml` shows the config shape with a general-reader objective.
