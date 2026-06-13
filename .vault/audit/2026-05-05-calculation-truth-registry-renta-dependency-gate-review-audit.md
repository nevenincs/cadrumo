---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-renta-dependency-gate-exec]]'
---



# `calculation-truth-registry` Code Review

REVIEW-001 | INFO | No findings
Reviewed the Modelo 100 dependency-classification gate implementation against
the May 3 ADR, May 3 plan, and Renta source-dependency reference. The schema
change preserves direct annual-settlement relation requirements while allowing
relation-free factual-evidence classifications. The validator adds hard
failure gates for unclassified relation sources, duplicate source ownership,
non-dependency relation sources, and missing relation coverage. The TOML data
matches the Renta dependency ledger categories, and the tests cover positive
classification shape plus negative validation paths, including the direct
annual-settlement relation-ref requirement. No correctness, safety, or
test-quality issues were found in the reviewed scope.

## Reviewed Scope

- `src/aeat/domain/calculations/registry/_schema.py`
- `src/aeat/domain/calculations/registry/_validate.py`
- `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- `registry/aeat/modelos/100.toml`

## Verification

- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_100_parity_tapes.py src\aeat\domain\calculations\registry\test_parity_tapes.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `git diff --check` passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py src\aeat\domain\calculations\registry\test_formula_runtime.py src\aeat\domain\calculations\registry\test_cross_dependency_calculations.py -q`
  passed.
