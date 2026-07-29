# Live hard-source collector pattern for CXO investment intelligence

Use this when upgrading a pilot evidence-ledger / source-universe system into a more live CXO intelligence feed.

## Goal

Move from static/source-target rows into auditable live signals while preserving the advisory boundary:

```text
watchlist.yaml
  ↓
hard_source_collectors
  ↓
source_universe_intake ranker
  ↓
topic_state change tracking
  ↓
CXO brief renderer + quality scan
```

The collector should produce research candidates, not conclusions or trade decisions.

## Minimal live sources that worked well

1. **SEC identity + recent filings metadata**
   - Map watchlist ticker → CIK via `https://www.sec.gov/files/company_tickers.json`.
   - Fetch latest filing metadata via `https://data.sec.gov/submissions/CIK##########.json`.
   - Candidate fields should say what is proven: filing form/date/document metadata.
   - `cannot_prove`: filing metadata does not prove business implication; body/transcript still needs reading.

2. **FRED live Treasury yield curve**
   - No-key CSV endpoint: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2` etc.
   - Useful starter series: `DGS2`, `DGS10`, `DGS30`.
   - Compute simple context such as `10Y-2Y spread`.
   - Candidate confidence can be `verified_data`, but causal claims must remain unproven.

3. **US/HK watchlist and market-proxy moves**
   - Use direct yfinance daily adjusted prices for configured US/HK equities/ETFs plus proxies such as `SPY, QQQ, IWM, XLK, SMH, TLT, UUP`.
   - Emit 1D and 60D moves as market-action candidates.
   - Treat Stooq as best-effort. Normalize Yahoo `0700.HK` to Stooq `700.hk`; never create a hybrid such as `0700.hk.us`.
   - A code path, HTTP 200, HTML challenge page, or importable module is not a successful second source. Confidence remains `market_data_probable` until usable same-date rows are parsed and reconciled.

4. **Watchlist relevance rows**
   - Use `configs/watchlist.yaml` to route relevance only.
   - Watchlist does not imply holdings, intent, position sizing, or investment merit.

## Candidate fields to preserve

At minimum:

```text
item_id
lane
title
summary
source
source_type
as_of_date
tickers
themes
source_url
source_authority
freshness
evidence_change
magnitude
novelty
decision_usefulness
portfolio_relevance
confidence
next_check
kill_signal
cannot_prove
```

## Runner verification markers

If this is wired into a full runner, assert markers for:

```text
primary_sec_identity
primary_sec_recent_filing
primary_macro_calendar
primary_macro_rates
primary_macro_fred_yields_live
market_proxy_prices_live
watchlist_config
cannot_prove
```

Also assert the normal advisory-boundary quality scan: no buy/sell/hold/add/reduce, no local paths, no implementation labels in reader-facing briefs.

## CXO rendering pitfalls

- Live data often arrives with source-language English. Translate `next_check`, `kill_signal`, and source summaries into natural Chinese before surfacing to the reader/CXO.
- A verified data point is not a verified explanation. Keep the distinction visible: “FRED says X” is source fact; “therefore equities moved because of rates” needs cross-evidence.
- SEC Form 4 / 8-K / 10-Q metadata should be pushed as “needs body read” unless the filing text has been parsed.
- Price moves should not be causal commentary until checked against a second source and event/news calendar.

## Suggested next step after minimal live collector

Add a second-source verification layer for market prices and make the CXO renderer convert all source wording into brief-quality Chinese. Do this before cron/auto-push.