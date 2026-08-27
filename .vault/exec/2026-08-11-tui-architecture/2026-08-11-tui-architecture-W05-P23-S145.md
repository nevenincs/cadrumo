---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:8cf7fd5492be8b8b7b20ff77142a7fc84e9f4433e878f8fa6e1551bb6d2be49e'
step_id: 'S145'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove strict protocol round trips, successful delivery, expiry and cancellation races, crash windows, restart classification, exactly-once release, sentinel non-retention, guarded edit compare-and-swap, effect-receipt narrowing, immutable production composition, and a semantic-plus-exact census that fails duplicate custody or edit authorities

## Scope

- `src/cadrumo/application/operations/tests/test_financial_operand_conformance.py and src/cadrumo/application/modelo/tests/test_edit_operation_conformance.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_financial_operand_conformance.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_conformance.py -m unit -n0` -> `pass`

## Notes

Discovery before building found nine of the Step's eleven named proofs
already real and passing elsewhere, discharged rather than duplicated (a
second copy of an already-proven fact drifts until one is wrong and
nothing notices):

- Strict protocol round trips, settlement disjointness, refusal reasons -
  `application/operations/tests/test_financial_operand.py`.
- Successful delivery, expiry/cancellation races, crash-window
  classification, restart reconciliation, exactly-once release, sentinel
  non-retention - `application/operations/tests/test_financial_operand_custody.py`
  AND, independently, at the persistence layer against real `tmp_path`
  storage, `adapters/persistence/operations/tests/test_financial_operand_custody.py`.
- Effect-receipt narrowing - `application/operations/tests/test_financial_operand_registration.py`.
- Guarded edit compare-and-swap - `application/modelo/tests/test_edit_execution.py`.
- Immutable production composition - checked directly rather than assumed
  unbuilt: `test_lifecycle_operation_conformance.py::test_every_exported_definition_reaches_the_production_registry`
  already composes the real `build_production_operation_registry()` and
  asserts `modelo.edit.apply` (the same operation this Step's own
  financial-operand declaration lives on) reaches it; three further files
  (`entrypoints/tests/test_no_dormant_operation_definitions.py`,
  `test_operation_composition.py`, `test_registered_executor_conformance.py`)
  compose the same production registry from other angles, and frozen-ness
  is separately covered generically (`test_capabilities.py`,
  `test_models.py`). The specific conjunction this Step names - a
  financial-operand-declaring operation and edit-apply both present in one
  composed, frozen production registry - is the SAME operation on both
  counts, so existing coverage already discharges it. No new code for this
  proof.

Only the census was genuinely absent (confirmed: zero hits for
`census`/`duplicate.*authorit`/`production composition` across
`application/operations/` before this Step). Built as a NEW, narrow file
rather than the two full files the Step names literally, per review: a
Step's file names describe intent, not a quota, and re-proving the nine
above would manufacture the inverse of today's other finding (a name
implying more than what's built) - a name implying LESS than what already
exists. `test_edit_operation_conformance.py` was not created; nothing
named in the Step required it once the residual was determined.

The census is scoped to `git ls-files *.py` from the start (never `rglob`
narrowed after the fact), asserted non-vacuous and stable
(`test_the_tracked_denominator_is_nonempty_and_reproducible`). Denominator
at the time of writing: several thousand tracked Python files repo-wide: a
looser floor of 1000 for now, sensitive to a checkout of clearly-wrong
size but not the whole-repo file count the campaign's other censuses have
already shown drift on. The two substantive checks: no two production
definitions declare the same `operand_kind` (a duplicate custody
authority), and exactly one production definition owns the Edit Contract's
`apply_modelo_edit` authority (a duplicate edit authority) - both run
against the real composed `build_production_operation_registry()`, not a
hand-listed set.
