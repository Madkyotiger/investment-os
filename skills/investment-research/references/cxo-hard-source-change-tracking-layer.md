# CXO hard-source + change-tracking layer

Use this when upgrading an investment research pipeline from a one-off thematic brief into a recurring CXO / founder intelligence system.

## Pattern

Do not jump from a pilot evidence ledger directly to cron pushes. Build the layers in this order:

1. Source-universe candidates
   - Normalize candidate rows across lanes: `macro_regime`, `company_events`, `sector_theme_discovery`, `market_action`, `portfolio_watchlist`.
   - Score for `source_authority`, `freshness`, `evidence_change`, `magnitude`, `novelty`, `decision_usefulness`, `portfolio_relevance`, and confidence.

2. CXO relevance
   - Maintain a profile config with role, business exposure, asset/watchlist exposure, current projects, relevance keywords, and push constraints.
   - Rank market candidates by personal relevance, not by generic market importance.
   - Render 3–5 items only: what changed, why it matters to the reader, what to ask, next source, kill/downgrade signal.

3. Topic state / change tracking
   - Store per-topic state between runs.
   - Compare the current candidate pool to the previous state.
   - Mark `new`, `updated_evidence`, `priority_changed`, `unchanged`, or `dropped_from_top_pool`.
   - Reader-facing output needs a natural “和上次相比” line. If nothing changed, say so; do not invent novelty.

4. Primary-source / watchlist hard-source layer
   - Start with source targets and identity rows before claiming live signal coverage.
   - Useful no-key first layer:
     - SEC ticker → CIK identity rows for watchlist symbols.
     - Fed calendar source target.
     - Treasury yield-curve source target.
     - Watchlist relevance rows.
   - Feed hard-source rows into the same source-universe ranker so they compete with thematic evidence instead of living in a separate report.

## Boundary rules

- Watchlist relevance is routing only, not holdings, trade intent, or investment merit.
- Do not touch real holdings unless the user explicitly approves.
- Do not open cron until manual runs have produced stable, useful briefs several times.
- `verified_source_target` means the source itself is authoritative, not that the current market implication has been proven.
- A hard-source target should carry `cannot_prove`, `next_check`, and `kill_signal` so it cannot masquerade as a complete conclusion.

## Minimal artifact set

```text
configs/watchlist.yaml
configs/cxo_profiles.yaml
src/<pkg>/hard_source_collectors.py
src/<pkg>/source_universe_intake.py
src/<pkg>/topic_state.py
src/<pkg>/cxo_intelligence.py
reports/hard-sources/hard_source_candidates.csv
reports/source-universe/source_universe_candidates.csv
reports/topic-state/topic_state.json
reports/topic-state/topic_changes.json
reports/cxo-intelligence/cxo_daily_brief.md
```

## Verification

Run both focused and full checks:

```bash
uv run pytest -q
bash scripts/run_us_china_pilot.sh
```

The run receipt should include:

- test count passed;
- hard-source candidate rows;
- source-universe candidate rows;
- changed topic count;
- CXO item count;
- evidence ledger row count;
- quality scans clean for trade-decision wording, local paths, internal implementation labels, and AI-style scaffolding.

## Common failure modes

- Letting a source target sound like a market conclusion.
- Allowing old pilot themes to crowd out hard-source rows; increase max candidates or rebalance scores.
- Rendering raw English source-target text into a Chinese CXO brief. Add translation/plain-summary handling for hard-source rows.
- Treating repeated daily output as “new” because there is no persisted topic state.
- Adding cron before the brief has survived manual review.