---
tags:
  - '#exec'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-source-kind-deferrals-plan]]"
---

# Extend the enrollment-status gate to assert every DEFERRED member carries both an owning ADR and a trigger annotation

## Scope

- `src/aeat/application/aggregation/tests/test_source_kind_enrollment_status.py`

## Description

- Author `application/aggregation/tests/test_source_kind_enrollment_status.py`: assert `DEFERRED_SOURCE_KINDS` is derived from the targets mapping, every deferred kind carries a non-empty owning ADR + trigger, and every owning ADR stem resolves to a real `.vault/adr` file.

## Outcome

The enrollment-status gate now asserts every deferred member is governed; a new deferred kind without owner+trigger fails loudly.

## Notes

The plan named `application/aggregation/tests/test_source_kind_enrollment_status.py` which did not exist; created it (the existing `test_source_boundary_and_enrollment.py` reads DEFERRED_SOURCE_KINDS but is a heavy integration suite — kept the annotation gate a focused unit test co-located with the declaration).
