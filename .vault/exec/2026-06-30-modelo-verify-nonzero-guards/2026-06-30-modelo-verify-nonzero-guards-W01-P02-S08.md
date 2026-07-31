---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:92f9e1a293a87de302dc4b3d7fff38247c90b2a88d7ce2c54f0f601105a6461b'
step_id: 'S08'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a gate-behaviour test calling evaluate_verification_predicates directly for the M123 06-to-09 advisory, proving FIRES on positive-06-zero-09, HOLDS on positive-06-positive-09, and trivial-HOLD on zero-or-negative-06

## Scope

- `src/aeat/application/modelo/tests/test_verification_m123_advisory.py`

## Description

- Created `src/aeat/application/modelo/tests/test_verification_m123_advisory.py` mirroring `test_verification_m131_advisory.py`, reusing the shared `_CASILLA_06`, `_CASILLA_09`, and `_workflow_profile()` fixtures already defined in `_verification_substance_support.py` (no new fixture casilla ids were needed).
- Loaded the predicate via `resources().modelos.authority.validate_modelo("123").revisions["2024-y-siguientes"]` and asserted its shape (`finding_kind == "ADVISORY"`, `expression == 'implies_nonzero(["06", "09"])'`).
- Wrote four gate-behaviour tests calling `evaluate_verification_predicates` directly (no hand-computed Decimal oracle, per `no-tautological-calculation-tests`):
  - legal grounding (`rd-439-2007:art-90`, `ley-35-2006:art-101` present on the loaded predicate).
  - FIRES: positive casilla 06 (42000.00), zero casilla 09 -> one ADVISORY/WARNING finding carrying the legal_ref.
  - HOLDS: positive casilla 06, positive casilla 09 -> no findings.
  - trivial-HOLD: zero-or-absent casilla 06 -> no findings (both explicit-zero and entirely-absent casilla_values mappings).

## Outcome

All four tests pass. Full command: `uv run --no-sync pytest src/aeat/application/modelo/tests/test_verification_m123_advisory.py -q` -> 4 passed. Combined run with the registry-shape test file (`test_modelo_123_registry.py` + `test_verification_m123_advisory.py`): 11 passed. A broader sanity pass (`pytest --collect-only -q src/aeat/domain/calculations/registry src/aeat/application/modelo`) collected 4331 tests with zero collection errors, and the registry validation/legal-grounding gate subset (`-k "validat or legal or referential"`) passed 569/569.

## Notes

No incidents. `ruff check` and `ruff format --check` both clean on the new test file (the sibling registry test file required one auto-format pass for pre-existing spacing, applied and re-verified green).
