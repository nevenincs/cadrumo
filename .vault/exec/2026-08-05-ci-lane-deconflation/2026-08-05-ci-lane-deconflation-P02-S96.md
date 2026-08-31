---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5a58dad1335118ab680500072b7b3ec1f788ec27b5065a604638ebb94ae4e4ab'
step_id: 'S96'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Sweep the codebase for the positional-selection defect class after hitting its third instance, and size it honestly rather than declaring fifty bugs. The class, established by three independent instances today: a test pins its subject by POSITION -- OWNERSHIP[-1], OWNERSHIP[:-1], the first filing record for a work unit, next(iter(modelo.revisions.values())) -- and silently tests the wrong thing, or dies on an empty search, the moment a sibling appears. All three read as data problems and were selection problems, which is what makes the class worth naming: the symptom never points at the cause. FIFTY candidate sites match next(iter(...revisions...)) across src/cadrumo. THEY ARE NOT FIFTY DEFECTS and must not be reported as such -- many operate on a synthetic single-revision modelo the test itself constructed, where taking the only member is correct and clearer than a search. The at-risk subset is specifically those reading a REAL bundled modelo that declares more than one revision. Two were sampled and both qualify: application/registry/tests/test_temporal_coverage.py takes registry_authority.modelo('341') and then its first revision, and modelo 341 declares two; domain/calculations/registry/tests/test_audit_oracle_bindings.py carries a DOUBLE positional assumption in _bind_oracle_id_on_first_cross_reference, taking the first revision AND then cross_references[0], so a first revision declaring no live cross-references raises IndexError rather than failing on its subject. Modelo 038, used the same way in test_filing_capability_worklist, also declares two. These pass today only because the first revision happens to carry what the test needs -- the exact condition that held for modelo 184 until four older revisions preceded the two that declare filing schedules. THE HEURISTIC IS THE DELIVERABLE, not a fifty-site sweep nobody will finish: when a test says 'the first', ask what happens when a second arrives, because in this repository a second always does -- peers add revisions and epochs continuously, and modelo 184 went from working to StopIteration by exactly that route. Fixing a site is cheap and local: select by the property under test, as the filing-schedule gate now does by matching period_kind across all revisions rather than searching only the first. Prioritise sites reading real multi-revision modelos; leave synthetic-fixture sites alone

## Scope

- `src/cadrumo/application/registry/tests/test_temporal_coverage.py`
- `src/cadrumo/domain/calculations/registry/tests/test_audit_oracle_bindings.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S96.md`
- `verify:` `pytest -q -n0 test_temporal_coverage.py::test_temporal_coverage_expands_open_selectors_through_the_supported_horizon test_audit_oracle_bindings.py::test_binding_to_test_environment_oracle_fails_under_production test_filing_capability_worklist.py::test_modelo_036_product_scope_terminal_is_exact_to_the_reviewed_revision` -> `3 passed in 43.93s`
- `verify:` `pytest -q -n0 test_temporal_coverage.py test_audit_oracle_bindings.py test_filing_capability_worklist.py` -> `51 passed, 1 unrelated failed in 158.41s`

## Notes

Immutable plan provenance is `293434861686`; no historical literal test receipt is recoverable. Subsequent P97-P99 reconciliation is decisive for the original inventory: `be1ad83404` corrected the M341 open-selector subject, while P99 establishes that the M130 helper is a one-revision deliberate mutation and the M038 use is only an adjacent-model negative control. The broad failure is `test_every_registry_revision_can_produce_a_filing_artifact`, which asserts an empty filing-capability worklist despite 35 enumerated no-layout revisions; it is unrelated to positional selection and is recorded rather than hidden.
