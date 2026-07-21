---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add a coverage-gate negative test where a populated undeclared namespace fails the sealed export

## Scope

- `src/aeat/application/bucket_maintenance/tests/test_custody_completeness.py`

## Description

- Add a negative coverage gate for populated namespaces not covered by full custody.
- Exercise the gate through real secure-object repository state.
- Keep failure at export time so incomplete sealed archives are not written.

## Outcome

- Complete. Full custody cannot silently omit a populated durable namespace.
- Verified by `test_custody_completeness.py` and reviewer pass.

## Notes

- The coverage gate remains registry-driven; derived and process-local exclusions are deliberate.
