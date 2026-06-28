---
step_id: S140
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P05.S140

Extended the test surface across all four migrated boundaries to cover the
coerce-vs-validate UTC semantics introduced by S139.

## Tests added

- `test_certificate.py` — `test_load_certificate_not_before_is_utc_aware`, `test_load_certificate_not_after_is_utc_aware`: assert both PKCS#12 timestamps on `LoadedCertificate` carry UTC tzinfo after `load_certificate` (coerce semantic).
- `test_manifest.py` — `test_created_at_naive_raises_validation_error`, `test_created_at_utc_aware_accepted`, `test_last_unlocked_at_utc_aware_accepted`: validate semantic rejects naive, accepts UTC-aware.
- `test_recovery_record.py` — `test_created_at_naive_raises_validation_error`, `test_created_at_utc_aware_accepted_and_preserved`, `test_created_at_non_utc_offset_raises_validation_error`: full validate-semantic coverage.
- `test_aggregate.py` — `test_aggregate_rejects_naive_created_at`, `test_aggregate_rejects_non_utc_created_at`, `test_aggregate_accepts_utc_created_at`: validate semantic at the aggregate boundary.

## Outcome

48 tests pass across certificate, manifest, recovery_record files.
12 tests pass in test_aggregate.py (isolated; transitive import-chain error in
`ClassificationRuleError` is a pre-existing unrelated regression).
