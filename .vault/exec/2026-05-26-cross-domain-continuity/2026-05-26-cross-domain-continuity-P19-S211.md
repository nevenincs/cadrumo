---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S211
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P19.S211 — tamper-detection regression test

## Outcome

Added `test_observation_tampering_is_detected_by_verify_path` to
`src/aeat/application/modelo/test_verification_substance.py`.

The test calculates an M130 revision normally, then constructs a tampered
`CalculationRevision` via `model_construct` (bypassing `_enforce_invariants`) with
the same `calculation_revision_id` but a mutated `casilla_values["02"]`. The tampered
revision is passed directly to `_assert_revision_content_integrity` which detects the
hash mismatch and raises `StoredCalculationDriftError`.

### Design note

The `_enforce_invariants` pydantic validator and `_assert_revision_content_integrity`
are functionally equivalent for the content-hash check: both re-derive the SHA-256 id
from the stored fields. Pydantic catches tampering at deserialization time; the
application-layer guard is a defense-in-depth layer for scenarios where pydantic
deserialization is bypassed (raw-storage injection, schema migration, `model_construct`
calls in application code). The test exercises the application-layer guard directly via
`model_construct` rather than going through storage, which would be re-caught by
pydantic's deserialization validators before reaching the application layer.

## Files changed

- `src/aeat/application/modelo/test_verification_substance.py` (S211 tampering regression test)
