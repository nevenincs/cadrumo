---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:83f1f81da691946918001d09114b6811c3b48bdcf87ed98dc54a3b4309f725e9'
step_id: 'S06'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
## Description

- Added `CasillaProducerProvenance` as a lossless typed trace for one revision-local casilla producer path.
- Projected formula, manual, upstream, relation-prefill, and informational reasons from the existing schema declarations.
- Retained formula, binding, relation, casilla, legal-reference, and source-reference identities without flattening relation declarations.
- Added real bundled-registry tests for all producer kinds, producer-specific references, relation multiplicity, and inventory coverage.

## Outcome

S06 is implemented as a typed schema inventory. Every loaded revision exposes a producer kind, explicit reason, and non-empty provenance trace for each declared casilla; relation-prefill bindings retain one trace per relation declaration. No registry data or production formula was changed.

## Notes

The inventory is descriptive and remains downstream of registry-authority validation. Legal/source and conformance report projection is intentionally deferred to S07 and S08. The delegated reviewer persona returned a checkpoint without a completed report; the supervisor completed the bounded review and recorded the consumer-projection boundary in the S06 audit.

## Verification

- `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” 8 passed.
- `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” all checks passed.
- `uv run --no-sync ruff format --check src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” 2 files already formatted.
- `uv run --no-sync basedpyright src/cadrumo/domain/calculations/registry/_schema.py src/cadrumo/domain/calculations/registry/tests/test_modelo_100_casilla_wiring_contract.py` â€” 0 errors and 2 pre-existing private-helper warnings.
- `git diff --check` on the S06-owned files â€” clean.
