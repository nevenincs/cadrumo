---
tags:
  - "#exec"
  - "#t6-aggregation"
date: 2026-04-30
related:
  - "[[2026-04-30-t6-aggregation-plan]]"
  - "[[2026-04-30-t6-aggregation-review]]"
---

# t6-aggregation verification execution

Final verification passed after review fixes.

Commands:

- `uv run --no-sync pytest src/aeat/financial/aggregation/test_aggregation.py src/aeat/cli/test_json_schema_conformance.py src/aeat/errors/test_registry.py src/aeat/errors/test_registry_enforcement.py -q` — 47 passed after adding the workflow inputs-provider handoff and Gemini regression tests.
- `uv run --no-sync pytest src/aeat/formulas/_rulesets/test_modelo_130_2024.py src/aeat/formulas/_rulesets/test_modelo_130_2025.py src/aeat/formulas/_rulesets/test_modelo_130_2026.py -q` — 54 passed.
- `uv run --no-sync pytest src/aeat/cli/test_json_pipe_safety.py -q` — 7 passed.
- `uv run --no-sync pytest src/aeat/cli/test_json_pipe_safety.py src/aeat/cli/workflow/test_cli_runtime.py -q` — 9 passed.
- `uv run --no-sync pytest src/aeat/financial/aggregation/test_aggregation.py src/aeat/workflow/test_live.py src/aeat/cli/workflow/test_cli.py src/aeat/cli/workflow/test_cli_runtime.py -q` — 16 passed, 1 deselected.
- `uv run --no-sync ruff check src/aeat/financial/aggregation src/aeat/cli/financial/aggregate.py src/aeat/workflow/_adapters.py src/aeat/financial/transactions/_repository.py` — passed.
- `just test-cov` — 5005 passed, 19 skipped, 24 deselected; total coverage 82.57%, above the 60% floor after Gemini fixes.

The full suite includes the Modelo 303 ruleset and filing tests; Modelo 303 T6 aggregation remains intentionally deferred by the ADR.
