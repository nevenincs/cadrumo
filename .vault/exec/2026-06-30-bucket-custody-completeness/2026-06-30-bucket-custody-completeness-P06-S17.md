---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S17'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add a registry test asserting every namespace declares a custody_disposition

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py`

## Description

- Assert every registered secure-object namespace declares a custody disposition.
- Assert representative structured, full-only, derived, and process-local namespaces resolve to the intended custody profiles.
- Keep the registry projection as the single source for carry-set membership.

## Outcome

- Complete. A new namespace without custody classification fails the registry test.
- Verified by `test_namespace_registry.py`.

## Notes

- This step was originally implemented alongside P01 but is recorded here against the plan row.
