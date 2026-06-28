---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-snapshot-filing-context-exec]]'
---



# `calculation-truth-registry` Code Review

One medium test-coverage issue was found and resolved before commit.

`calculate_registry_snapshot` now validates relation values against
`snapshot.period`. Initial coverage only proved that `build_snapshot` preserved
the selected filing context. The runtime branch now has a focused regression
test that derives a Modelo 180 edge-case snapshot with an inactive relation
period and proves annual-summary relation values are rejected when they are not
active for the selected period.

No blocking issues remain. The selected filing year and period are appropriate
first-class snapshot context because they are selected by `build_snapshot`,
validated during revision selection, and then consumed by runtime relation
validation.

Verification recorded after resolution:

- `uv run pytest src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_snapshot.py src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/_snapshot.py src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_formula_runtime.py`
