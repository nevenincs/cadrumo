---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-adjacent-modelo-registry-closure-exec]]'
---



# `calculation-truth-registry` Code Review

REVIEW-001 | INFO | No findings
Reviewed the adjacent Modelo 202, 232, and 349 registry closure work against
the central registry ADR and plan gates. The changes add missing
application-link, construct, and static cross-reference coverage without adding
new calculation authority outside the registry. Modelo 202 calculation coverage
uses existing registry formulas, Modelo 232 remains informative-only, and
Modelo 349 remains manual/informative with static documentation guarded from
remote writes. No correctness, safety, or test-quality issues were found in
the reviewed scope.

## Reviewed Scope

- `registry/aeat/modelos/202.toml`
- `registry/aeat/modelos/232.toml`
- `registry/aeat/modelos/349.toml`
- `src/aeat/domain/calculations/registry/test_modelo_202_registry.py`
- `src/aeat/domain/calculations/registry/test_modelo_232_registry.py`
- `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`

## Verification

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py`
  passed.
- `git diff --check` passed with a pre-existing CRLF warning in
  `src/aeat/locales/en.yml`.
