---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:062cd7aa88d7ef2cb9d40894943e910c98bef6aa9e7e4c119c381df95d541f30'
step_id: 'S23'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
## Scope

- Add the frozen application-owned `ModeloWorkReview` and its single `build_modelo_work_review` producer.
- Resolve the law-determined registry revision, assert stored work/revision identity, and join persisted calculation and verification state through canonical derivations.

## Description

- Project every revision casilla with official classification/reference, declared input kind, concrete binding/formula/relation lineage, realised value kind, legal/source grounding, findings, and shared blocker references.
- Use only persisted replay facts for historical realised-origin classification; split decimal, enum, and date binding channels through canonical registry inventories.
- Emit `OPERATOR_OVERRIDE` only when a non-empty persisted bound-value set actually diverges from the persisted observation; equal, absent-by-design, or uncomparable origins make no unsupported anomaly claim.
- Preserve S24 finding-attribution and S25 progress ownership boundaries.

## Outcome

- The facade exposes the exact sole `ModeloWorkReview` class and `build_modelo_work_review` producer.
- A law-resolvable work target with no calculation renders an empty realised layer and nullable verification; persisted M130 calculations render formula and binding lineage; persisted M100 ISO date bindings render without decimal reinterpretation.
- Canonical `BucketId`, `ModeloCode`, `WorkUnitId`, and `CalculationRevisionId` types remain intact at the read boundary.
- Formal review passed after all date-channel, historical-origin, and typed-identity findings were resolved.

## Verification

- `pytest -q -n0 src/cadrumo/application/modelo/tests/test_modelo_work_review.py`: 3 passed using real encrypted repositories and bundled registry authority.
- Scoped Ruff passed.
- Scoped BasedPyright passed with 0 errors, warnings, or notes.
- `just audit-duplication`: no clones across 1508 analysed files.
- Facade identity, sole-declaration, prohibited-test-construct, and scoped diff checks passed.

## Notes

- One initial rerun honestly refused while concurrent registry writes changed the fingerprint; the clean post-write reruns passed.
- No fake, stub, mock, patch, monkeypatch, skip, xfail, compatibility alias, wrapper, or duplicate authority was introduced.
