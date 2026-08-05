---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:9c2357f5eac61084d39d139ab800b0f21344f492f89b6aa02c44a33e0947ca45'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
---
## Scope

Reviewed W01.P04.S06 against the accepted five-domain parity contract, the denominator research, and the execution plan. The review covered the current S06 delta in `src/cadrumo/domain/calculations/registry/_schema.py` and the real bundled-registry contract tests in `src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py`. The delegated reviewer persona returned a checkpoint without a completed report, so the supervisor performed the final bounded review.

## Findings

### consumer-projection | medium | The typed producer inventory is not yet consumed by the legal/source or conformance reports

S06 now exposes lossless formula, manual, upstream, relation, and computed producer traces with producer-specific legal/source references, but no registry-wide report consumes those traces yet. This is an intentional phase boundary: S07 must build construct-level legal/source rows and S08 must separate evidence-floor results from per-casilla provenance in conformance output. Until those steps land, S06 is an auditable schema surface rather than a complete parity report.

### validator-boundary | low | Producer traces are descriptive and depend on the existing registry validation boundary

`producer_inventory()` preserves malformed or incomplete states as explicit reasons, while `src/cadrumo/domain/calculations/registry/_validate.py` remains responsible for rejecting invalid formula/casilla wiring. Consumers must therefore validate through the registry authority before treating a trace as an accepted producer. This separation is consistent with the accepted ADR and keeps measurement from silently repairing bad declarations.

### relation-multiplicity | low | Relation provenance remains distinct per declaration

The implementation emits one trace per relation declaration targeting a relation-prefill binding and retains each relation's own legal/source references. The real bundled-registry test exercises a binding with multiple relation declarations and verifies that no relation identity or provenance is flattened.

## Recommendations

- Carry `consumer-projection` into W01.P05.S07 and W01.P05.S08; project the typed traces without deriving new legal or source claims.
- Keep registry-authority validation ahead of any report or CLI projection.
- Preserve one relation trace per declaration, including its relation id and producer references, in later cross-model and conformance rows.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” 8 passed.
- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” all checks passed.
- `uv run --no-sync ruff format --check src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” 2 files already formatted.
- `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” 0 errors and 2 pre-existing private-helper warnings in the test support import.
- `git diff --check` on the S06-owned files â€” clean.
- No staging, commits, registry-data changes, or unrelated WIP changes were made.
