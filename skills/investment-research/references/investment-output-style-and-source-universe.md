# Investment Output Style & Source Universe Notes

Use this when turning evidence ledgers, expert signals, market data, filings, or source-check queues into the user-facing investment research output.

## First-principles target

The output is useful only if it helps decide where research time should go next. A clean pipeline, ledger, queue, or source crosswalk is infrastructure; it is not the investor-facing product.

Before choosing style, lock the product seat:

- **Product A Daily Scan** — broad, current, multi-item browsing;
- **Product B Triggered Rolling Deep Read** — one decision-worthy current delta, interpreted through longitudinal history to the next material event;
- **Stock / Question Deep Pack** — on-demand special-study mode only when explicitly requested and source coverage is sufficient.

A fixed narrow question or six-to-twelve-month forecast can be rigorous research and still fail as a recurring reader product. See `references/daily-scan-vs-triggered-rolling-deep-read.md`.

The reader-facing product should answer:

- Which topics deserve research time now?
- Which are interesting but still too story-driven?
- What source or variable would change the view?
- Which company names are worth making into research cards?
- What can safely be ignored until there is new evidence?

Do not make the reader look at system internals.

## Two-tier output

1. **Detailed pack**
   - For Product A: expands only current items with enough evidence or unresolved risk.
   - For Product B: pulls the historical prior for one material current delta, explains what changed, and assesses the path to the next decisive event.
   - For an on-demand Stock/Question Deep Pack: model depth and multi-source comparison may expand further, but it is not the recurring default.
   - Organizes by research action, not database category.
   - Useful Product A buckets: `最先花时间`, `留在观察区`, `只能当底图`, `现在先别急`.
   - Include evidence, missing variables, next source target, company names to watch, and trigger/kill signals.

2. **Daily brief / short surface**
   - One Feishu/WeChat phone screen for Product A.
   - Lead with one judgment.
   - 1-5 short bullets max; fewer or zero is fine.
   - End with the one research action worth doing today.
   - No implementation language, no internal file names, no source-system labels.
   - Do not force Product B depth into the daily short surface.

## Natural Chinese finance style

Avoid visible template scaffolding. These labels make the output smell like GPT even when the facts are right:

- `为什么看：`
- `现在看到的证据：`
- `还差什么：`
- `下一步：`
- `可以先盯的名字：`
- `今天先看三件事：`
- `一句话：`
- `这份东西不是...`

Prefer paragraph or bullet prose that sounds like an investment note:

> 今天先放一个判断：AI 基建这轮，别只看 GPU。更值得先查的是内存 / 被动件、机房电力 / 散热；网络 / 光通信 / CPO 继续放在观察区。

Not:

> 一句话：这轮 AI 基建不要只盯 GPU。今天先看三件事：...

Technical English should survive only when it is the natural market term: HBM, DRAM, MLCC, CPO, ASP, GPU, capex, FCF. Translate process English such as `source verification`, `queue`, `category`, `status`, `deployment timing`, `supplier filings`, `segment revenue` into Chinese finance language.

## Source universe rule

AI infrastructure is a pilot topic, not the system boundary.

Daily investment intelligence should select across a broad source universe:

- macro regime: rates, dollar, credit, liquidity, volatility, indexes;
- company events: earnings, filings, guidance, buyback/dividend, M&A, management commentary;
- sector/theme discovery: AI infra, energy, grid, healthcare, consumer, financials, industrials, China policy/demand/export chains;
- market action: price, volume, breadth, factor, sector ETF leadership, unusual moves;
- expert/media signals: X/newsletters/specialists/media as question fuel, not truth;
- portfolio/watchlist relevance: candidate names and exposure implications, without trade instructions.

Rank daily items by decision usefulness, evidence change, novelty, magnitude, source quality, and portfolio/watchlist relevance. Exclude repeated themes without new evidence, pure hype, uncheckable opinion, and trade instructions.

## Regression gates to encode in code/tests

- boundary scan: no buy/sell/hold/add/reduce/position sizing language;
- external leakage scan: no local paths, commands, repo/pipeline labels, or internal file names;
- technical smell scan: no evidence ledger / source verification / P0 / queue / renderer / schema / category / status;
- AI-style scan: no visible scaffolding labels listed above;
- readability spot check: no long English process fragments and no awkward punctuation such as `。，`, `但CPO`, `先补 先`, `先补 把`.
