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

# 2. The agent researches and writes RUN/live-packet.json plus RUN/evidence/*

# 3. Validate the packet, select qualifying items, store the run
uv run investment-os radar evaluate \
  --packet RUN/live-packet.json --config configs/upstream_radar.sample.yaml \
  --out RUN/output --run-dir RUN --db reports/upstream-radar/radar-index.sqlite

# 4. After the agent has written and reviewed the final text, attach it and re-validate
uv run investment-os radar evaluate ... --delivery-file RUN/final.md

# Read back the stored state
uv run investment-os radar store readback --db reports/upstream-radar/radar-index.sqlite
```

`preflight` writes the full manifest and a compact `seen-state-digest.json` to read first. A missing or empty database blocks preflight: an empty history must be rebuilt on purpose, not assumed.

`evaluate` exits `0` on `pass` and `1` otherwise. It writes `reader-brief.md` (a worksheet rendering), `selected-items.json`, `run-receipt.json` and `delivery-final.md` under `--out`. The receipt always records `claim_sent: false`: a rendered or stored text is not proof of delivery.

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

## What stays outside this repository

Reader lists, delivery channels, schedules, the real source pool and run history belong to the deployment. `configs/upstream_radar.sample.yaml` shows the config shape with a general-reader objective.
