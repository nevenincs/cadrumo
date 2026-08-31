---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4a6f2d64d5a86182ee1686f0efbe61ff3e44d0e3ea236465ebe4c362234a3dbb'
step_id: 'S94'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Implement the accepted-set on NoRevisionForPeriodError and end the silent branch that consumed it, closing the operator-facing half of the Modelo 390 exercise-2026 gap. DEMONSTRATED ON THE REAL CASE, not on a synthetic one: requesting modelo 390 filing_year 2026 period 0A through the bundled authority now raises 'modelo 390: no revision for year=2026 period=0A revision=None; modelo 390 declares: 2021, 2022, 2023, 2024, 2025', with available_revision_ids carrying that tuple structurally. An operator who previously could not distinguish a broken application from an unpublished orden is now told exactly which years exist, which is the whole difference between an apparent malfunction and an accurate statement about the world. THE PARAMETER IS REQUIRED, NOT DEFAULTED, and that was the deliberate choice: a default would let a future raiser silently ship the uninformative form, which is the same empty-filter hazard this campaign has guarded against all along. It is safe to require because there are exactly two construction sites, both in temporal.py, both already holding the modelo's revision collection, and no test constructs the error directly -- so there is no case where the accepted set is genuinely unknown. It follows the sibling AmbiguousRevisionSelectionError's established shape: sorted tuple attribute, _csv into the structured context, named in the fallback text, and appended to the message only when non-empty. THE CONSUMER FIX FOLLOWS THE DISCIPLINE THE CODE ITSELF DOCUMENTS: the NoRevisionForPeriodError branch in _binding_readiness.py returned None with no log while its two sibling branches logged, so a developer debugging undetermined profile bindings got diagnostics for two of three causes and silence for the common one. It now logs, quoting the error rather than composing a second copy -- exactly what the ambiguous branch's own comment says to do, because a locally restated remedy drifts from the selector's advice. The None-means-undetermined contract is untouched. VERIFICATION IS INCOMPLETE AND THAT IS STATED RATHER THAN GLOSSED: the behaviour itself is proven by the live authority call above, and ruff is clean on all three files, but the regression run over test_m390_temporal_epochs, test_filing_schedule_selection and test_binding_readiness could NOT complete -- a peer's uncommitted work in domain/contribuyente leaves SUPPORTED_PROFILE_SCHEMA_VERSION undefined and the package unimportable. That is peer WIP of the kind that has self-healed repeatedly today, and their files were not touched. Re-run those three modules narrowly once the tree imports again

## Scope

- `src/cadrumo/domain/calculations/registry/errors.py`
- `src/cadrumo/domain/calculations/registry/temporal.py`
- `src/cadrumo/application/modelo/_binding_readiness.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_temporal.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S94.md`
- `verify:` `python -m pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_temporal.py::test_modelo_390_2026_refusal_lists_the_enrolled_revision_set` -> `pass`
- `verify:` `python -m py_compile src/cadrumo/domain/calculations/registry/tests/test_temporal.py` -> `pass`
- `verify:` `ruff check src/cadrumo/domain/calculations/registry/tests/test_temporal.py` -> `pass`
- `verify:` `git diff --check -- src/cadrumo/domain/calculations/registry/tests/test_temporal.py` -> `pass`

## Notes

The current regression hunk is immutable commit `565f31c494`; this traceability successor does not duplicate or rewrite it. Historical implementation provenance is `be1ad83404`, whose literal pytest output is not recoverable. This record attests the current focused regression receipt only.
