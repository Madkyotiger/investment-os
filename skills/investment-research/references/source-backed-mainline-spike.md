# Source-backed investment research mainline spike

Use this reference when moving an investment-research prototype from price-only watchlist reports toward a proven, source-backed workflow mainline.

## Architecture choice

For the reader's personal / friends / client-reference investment research system, the stronger architecture is not a single large terminal repo and not ad-hoc repo stitching. Use mature modules by capability, with the active project or research system owning schema, evidence status, report policy, and advisory boundary.

Optional deep-research tracer bullet, not the recurring daily dependency baseline:

```text
OpenBB price/history
+ FinanceToolkit financial statements and ratios
+ edgartools SEC filing metadata
→ Evidence Ledger CSV/JSON
→ client-safe research memo
→ no trade decision
```

## Why this order for a bounded deep-research spike

- **OpenBB** proves a mature global data/tooling base and can later expose Python/REST/MCP surfaces.
- **FinanceToolkit** adds transparent financial statement and ratio calculation, making the report more professional than price/news summaries.
- **edgartools** grounds US equity reports in SEC filing metadata and links, giving LLM/editor layers something to cite.
- **Local DataOS** must still own `source`, `as_of_date`, `freshness`, `status`, report schema, and no-decision checks.

## Minimal implementation shape

Add a separate spike pipeline rather than bloating the baseline price pipeline:

```text
src/<package>/spike1_research_memo.py
reports/spike-1/research_memo.md
reports/spike-1/evidence_ledger.csv
reports/spike-1/evidence_ledger.json
tests/test_spike1_research_memo.py
```

Dataclasses that worked well:

```python
EvidenceItem(symbol, category, claim, value, source, as_of_date, freshness, status, url='', note='')
SymbolResearchMemo(symbol, generated_at, evidence=[], evidence_gaps=[], research_suggestions=[])
```

Each adapter returns `(evidence_items, gaps)` and never writes directly to the report. The renderer consumes only evidence/gaps/suggestions.

## Dependency and setup notes

- Pin runtime to Python 3.11/3.12 when using OpenBB in this stack: `requires-python = ">=3.11,<3.13"`.
- Useful dependencies: `openbb`, `financetoolkit`, `edgartools`, plus existing `pandas`, `pyyaml`, `yfinance`, `pytest`.
- `FinanceToolkit` can return some statements/ratios without `FMP_API_KEY` via fallback paths; mark that in source notes. Do not imply premium/full coverage if no key is configured.
- `edgartools` needs SEC identity. Prefer `SEC_EDGAR_IDENTITY`; a generic private-research identity can be used for a local spike, but client/production use should set a real contact.

## Verification gate

Run:

```bash
uv lock
uv run pytest
uv run python -m <package>.spike1_research_memo --symbols AAPL MSFT --out reports/spike-1
```

Then verify:

- report exists;
- evidence ledger CSV/JSON exists;
- evidence rows > 0;
- report contains OpenBB, FinanceToolkit, edgartools, and Evidence Ledger Extract;
- forbidden decision phrases are absent: `建议买入`, `建议卖出`, `建议持有`, `建议加仓`, `建议减仓`, `目标收益`, `自动下单`.

## Pitfalls

- Do not let FinanceToolkit/edgartools/OpenBB own final claims. They provide evidence; DataOS decides status and report wording.
- Do not let missing fields become fluent prose. Missing/stale/conflicting fields must become `evidence_gaps`.
- Do not start with TradingAgents. First create the evidence layer it must cite.
- Do not use FinceptTerminal as the code base for Phase 1; use it as terminal/UX/workstation benchmark only.
- Do not let wrapper scripts become the proof. Direct module execution and test output are the proof; scripts are convenience after the core path is verified.
