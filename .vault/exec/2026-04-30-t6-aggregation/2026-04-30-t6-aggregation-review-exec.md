---
tags:
  - "#exec"
  - "#t6-aggregation"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-t6-aggregation-plan]]"
  - "[[2026-04-30-t6-aggregation-review-audit]]"
---

# t6-aggregation review execution

Completed mandatory `vaultspec-code-review` after implementation.

Findings addressed:

- Workflow now falls back to JSON inputs when no transaction catalogue envelope exists.
- Mixed transactions now apply both `business_pct` and category-profile proportionality.
- Modelo 130 expense mappings now reject computed/result casillas.
- Human CLI headers now use trilingual `Translatable` messages.
- Root CLI imports no longer initialize storage/Alembic and pollute JSON stderr.

Verification after fixes:

- `uv run --no-sync pytest src/aeat/domain/financial/aggregation/test_aggregation.py -q`
- `uv run --no-sync pytest src/aeat/application/workflow/test_live.py src/aeat/entrypoints/cli/workflow/test_cli.py src/aeat/entrypoints/cli/workflow/test_cli_runtime.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_json_pipe_safety.py -q`
- `uv run --no-sync ruff check src/aeat/domain/financial/aggregation src/aeat/entrypoints/cli/financial/aggregate.py src/aeat/application/workflow/_adapters.py src/aeat/domain/financial/transactions/_repository.py`
