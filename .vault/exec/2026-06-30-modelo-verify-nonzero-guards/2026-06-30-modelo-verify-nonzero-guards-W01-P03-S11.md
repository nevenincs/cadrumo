---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Add a gate-behaviour test calling evaluate_verification_predicates directly for the M151 base-liquidable-to-cuota-integra advisory, proving FIRES on positive-base-zero-cuota, HOLDS on positive-base-positive-cuota, and trivial-HOLD on zero-or-negative-base

## Scope

- `src/aeat/application/modelo/tests/test_verification_m151_advisory.py`

## Description

- Created `src/aeat/application/modelo/tests/test_verification_m151_advisory.py` mirroring `test_verification_m131_advisory.py`. M151 has no shared casilla fixtures for the dotted impatriado ids in `_verification_substance_support.py`, so the two casilla ids (`impatriado.base-liquidable-general`, `impatriado.cuota-integra-general`) are constructed locally via `validated_casilla_id`; the shared `_workflow_profile()` fixture is reused.
- Loaded the predicate via `resources().modelos.authority.validate_modelo("151").revisions["2015-y-siguientes"]` and asserted its shape (`finding_kind == "ADVISORY"`, exact `expression` string).
- Wrote four gate-behaviour tests calling `evaluate_verification_predicates` directly (no hand-computed Decimal oracle, per `no-tautological-calculation-tests`):
  - legal grounding (`ley-35-2006:art-93` present on the loaded predicate).
  - FIRES: positive base liquidable (85000.00), zero cuota integra -> one ADVISORY/WARNING finding carrying the legal_ref.
  - HOLDS: positive base liquidable, positive cuota integra (20400.00) -> no findings.
  - trivial-HOLD: zero, negative, and entirely-absent base liquidable -> no findings in all three shapes.

## Outcome

`uv run --no-sync pytest src/aeat/application/modelo/tests/test_verification_m151_advisory.py -q` -> 4 passed. Combined run with the registry-shape test file (`test_modelo_151_registry.py` + `test_verification_m151_advisory.py`): 10 passed. A scoped registry validation pass (`pytest src/aeat/domain/calculations/registry -k "151 or build_snapshot or validate" -q`) collected and passed 82 tests with zero failures.

## Notes

No incidents. The locale key the new ADVISORY finding message resolves through (`application.modelo.findings.modelo_151_base_liquidable_implica_cuota_integra`) was authored via `python -m aeat.locales set` for all four locales (en/es/ca/hu) per `aeat-locales-cli`, since the dynamic `tr()` key built from `predicate_id` is not discoverable by `aeat.locales scaffold`'s static-call-site scan (the same pattern the M200/M131 predicates already required). `python -m aeat.locales audit` confirms no drift on the new key; the residual `cli.app.modelo.work.revision_verbose_help` gap reported by `audit`/`test_parity.py` pre-exists this feature (unrelated CLI help text) and is out of this Step's scope.
