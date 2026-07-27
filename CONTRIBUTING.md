# Contributing

Keep changes small and testable.

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest -q
uv run investment-os demo --out /tmp/investment-os-demo
uv run python scripts/public_release_guard.py
```

A change must preserve the research boundary: no buy/sell/hold instruction, position sizing, brokerage action, or unsupported promotion from metadata to conclusion.

Do not add real user data or downloaded source bodies to tests. Use synthetic fixtures with invented values and explicit source-status labels.
