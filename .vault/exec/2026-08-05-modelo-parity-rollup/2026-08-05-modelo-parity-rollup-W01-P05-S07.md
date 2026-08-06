---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:68d727fbf53c52b21821ee1b6198a9ba65774bd732df923356e5296e0770c854'
step_id: 'S07'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
## Description

- Grounded the construct evidence design in the accepted parity ADR, denominator research, plan, and vaultspec-rag discovery.
- Added typed revision-level evidence rows for formulas, parameters, bindings, relations, and binding-owned selectors.
- Preserved declaration-owned legal/source refs and marked selector refs as explicitly inherited from the owning binding.
- Added registry-wide authority validation, complete revision enumeration, duplicate-coordinate rejection, and real incomplete-ref tests.

## Outcome

S07 is implemented. The registry-wide construct evidence audit enumerates one exact row per formula, parameter, binding, relation, and selector across every validated modelo revision. The audit reports no current unresolved or unmeasured rows in the bundled registry and keeps construct evidence separate from revision floors and casilla producer provenance.

## Notes

No legal interpretation, selector semantics, formula, relation, or model data was changed. The conformance/report consumer remains intentionally open for S08. The delegated Luna-Max workers did not return a completed implementation or review report; the supervisor completed the bounded implementation review and recorded the consumer-projection boundary in the S07 audit.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_construct_evidence.py` â€” 3 passed.
- `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py -k "coverage" src/cadrumo/domain/calculations/registry/tests/test_construct_evidence.py` â€” 4 passed.
- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_coverage.py src/cadrumo/domain/calculations/registry/__init__.py src/cadrumo/domain/calculations/registry/tests/test_construct_evidence.py` â€” all checks passed.
- `uv run --no-sync ruff format --check src/cadrumo/domain/calculations/registry/_coverage.py src/cadrumo/domain/calculations/registry/__init__.py src/cadrumo/domain/calculations/registry/tests/test_construct_evidence.py` â€” 3 files already formatted.
- `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/_coverage.py src/cadrumo/domain/calculations/registry/__init__.py src/cadrumo/domain/calculations/registry/tests/test_construct_evidence.py` â€” 0 errors and 1 private-support warning.
- `git diff --check` on the S07-owned tracked files â€” clean.
