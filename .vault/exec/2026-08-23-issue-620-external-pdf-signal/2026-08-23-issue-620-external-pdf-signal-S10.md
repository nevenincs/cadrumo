---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f46ccbf1febae8f0c9df136f15214fc2cdd98380e1b24708139659d1181de7fd'
step_id: 'S10'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Resolve final review findings for the M036 route, exact candidate topology, and synthetic-corpus terminology

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests/test_external_layout_candidate_matrix.py`
- `src/cadrumo/tests/fixtures/external_layout_candidates/tests/test_candidate_contract.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Exercise Modelo 036 through its valid censal `alta` period and assert the exact blank result.
- Reject surprise candidate directories, root files, modelo files and orphaned JSON/PDF pair halves.
- Replace misleading real-corpus terminology in the synthetic justificante gate tests.
- Keep production parser and registry behavior unchanged.

## Outcome

Both Modelo 036 candidates now classify as `blank_no_values` with only `decl.event-kind` missing and empty value, malformed and ambiguous buckets. The matrix no longer swallows registry snapshot errors or exposes an unused unavailable outcome.

The candidate admission gate now requires exactly five modelo directories, exactly the `plain` and `fillable` JSON/PDF pairs in each directory, and no surprise corpus-root file or candidate directory. Ruff passed for all four changed modules. The focused unit run covering the matrix, candidate contract and two registry gate modules passed 57 tests in 44.70 seconds.

## Notes

Only tests and test wording changed. No production source, candidate byte or sidecar changed.
