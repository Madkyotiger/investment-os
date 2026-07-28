# US-first + China Unified Pilot Pattern

Use this when the user asks to keep Global US-prioritized while also proving China data in the same investment research system.

## Core stance

Do not expand “Global” into every market too early. Treat Phase 1 as:

```text
US-first Global core
+ China parallel branch
→ one Data Quality Gate
→ one Evidence Ledger
→ no-decision research memo
```

Other global markets are deferred until US and China both run cleanly.

## Implementation pattern

1. Keep US and China as separate data lanes but a shared contract.
2. Use one Evidence Ledger schema across lanes:
   - `symbol`
   - `category`
   - `claim`
   - `value`
   - `source`
   - `as_of_date`
   - `freshness`
   - `status`
   - `url`
   - `note`
3. Generate a compact summary memo with lane summaries, not full duplicated row dumps.
4. Keep detailed rows in CSV/JSON ledger artifacts.
5. Run a boundary scan on the final memo for forbidden decision language.
6. If a credentialed source is unavailable, keep it as explicit evidence (`token_missing`, `missing`, runtime date), not a silent omission.

## Good pilot shape

Default first proof set:

- US: large liquid equities across relevant sectors, e.g. AAPL / MSFT / NVDA / GOOGL / AMZN.
- China: one broad ETF plus one index, e.g. 510300 / 000300.

Outputs:

```text
reports/us-china-pilot/us_china_pilot_memo.md
reports/us-china-pilot/us_china_evidence_ledger.csv
reports/us-china-pilot/us_china_evidence_ledger.json
reports/us-china-pilot/boundary_scan.json
```

## Boundary scan phrases

At minimum scan for:

```text
建议买入 / 建议卖出 / 建议持有 / 建议加仓 / 建议减仓 / 目标收益 / 自动下单
recommend buy / recommend sell / recommend hold
```

Any non-zero hit blocks friend/client-facing use until rewritten or policy-filtered.

## Pitfalls

- Do not call China “secondary” if the user’s goal is US priority plus China proof. The correct language is “US-first core + China parallel branch.”
- Do not start adding Europe/Japan/HK/crypto just because OpenBB can reach them. First prove US + China stability, cache, field reconciliation, and reporting boundaries.
- Do not hide SEC filing parser gaps. Section heading variance should appear as explicit evidence gaps until parser hardening is done.
- Do not let a summary memo become a pseudo recommendation. It should point to research queue items and evidence gaps, not an investment answer.
