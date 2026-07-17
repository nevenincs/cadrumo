---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S63'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Follow-up: fingerprint the profile-activity relation-scoping inputs (activity_start_date, m111_no_retenciones_periods, not_applicable_source_modelos from ProfileRepository) in the approval basis, so a relation-scoping profile change invalidates an approval even when the observation store is unchanged

## Scope

- `src/aeat/application/filing/_review.py`

## Description

- Add a `profile_activity_fingerprint` field to `ModeloApprovalBasis` in `src/aeat/domain/filing/_schema.py` and bump `APPROVAL_BASIS_VERSION` from `review-basis-v3` to `review-basis-v4` (delete/replace, no compatibility shim per the no-legacy discipline).
- Add a `PROFILE_ACTIVITY_CHANGED` member to `ModeloApprovalStaleReason` and a `describe_stale_reason` case arm in `src/aeat/application/filing/_review.py`.
- Add the self-load helper `_load_profile_activity_fingerprint(bucket_id)` reading `record_to_path_values(ProfileRepository().load(bucket_id).record)` (ProfileNotFound to empty), the order-independent `_profile_activity_fingerprint(mapping)` digest, and the public `empty_profile_activity_fingerprint()` override, mirroring the invoice and prior-filing source fingerprints.
- Thread the `profile_activity_fingerprint` override parameter through `compute_current_approval_basis`, `approval_stale_reasons`, `approve_draft`, and `refresh_review_status`, and add the stale comparison; export the empty helper from `src/aeat/application/filing/__init__.py`.
- Thread the empty override at the shared leverage point `build_registry_filing_draft` in `src/aeat/application/filing/_testing_registry.py` and the four `approve_draft` fingerprint tests in `test_filing.py`; add the enum member to the describe-coverage map in `test_review_describe_stale_reason.py`; add `profile_activity_fingerprint` to the two `ModeloApprovalBasis` roundtrip construction sites in `test_roundtrip_anti_tautology.py` and `test_secure_storage_roundtrip.py`.
- Add the locale key `application.filing.review.stale_reasons.profile_activity_changed` in en/es/ca/hu through the locale CLI.
- Add `test_review_profile_activity_staleness.py`: two real-adapter integration tests (real `config profile create` to approve to `config profile edit`, asserting the sole `PROFILE_ACTIVITY_CHANGED` reason; anti-tautology with an unchanged real profile asserting no reason and a non-empty loaded digest) plus three registry-free fingerprint units (change-detection, order-independence, empty-vs-populated).

## Outcome

Closes the last calculation-source-connectivity staleness gap: a taxpayer profile change to a relation-scoping fact (activity-start date, m111 no-retenciones attestation, declared income categories) now invalidates an approved draft, because the approval basis fingerprints the whole wizard-free profile projection (the same `record_to_path_values` view the relation resolver reads) self-loaded from `bucket_id`. Coarse-safe: any profile-fact change invalidates, never under-invalidating. The filing application and domain suites pass (295 tests, sequential); ruff and ty clean. Plan reaches 63 of 63 (100%).

## Notes

The field, version bump, enum, describe arm, self-load helper, and same-commit threading (`_schema.py`, `_review.py`, `__init__.py`, `_testing_registry.py`, `test_filing.py`, `test_review_describe_stale_reason.py`, and the two domain roundtrip sites) landed at HEAD through the fleet commits (the same out-of-band mechanism observed on S62); the trailing commit `1df430a573` carries the remaining locale keys and the new staleness test file with an explicit pathspec (zero foreign markers verified). The integration tests provision a genuinely loadable profile through the real `config profile create`/`edit` CLI under `isolated_profile_storage_root`, because `ProfileRepository.load` requires the full mint sequence (bucket directory, manifest, wrapped DEK, encrypted record) that a bare lifecycle-record write does not produce; a partial-record seed self-loads as ProfileNotFound and would make the anti-tautology test pass vacuously (empty-equals-empty), so the change test additionally asserts the loaded digest is non-empty to prove the profile was really read.
