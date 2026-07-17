---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Prove operation-owned deletion rejects mismatches and accepts only journal-proven absence

## Scope

- `src/cadrumo/application/bucket_maintenance/tests/test_service_delete.py`

## Description

- Prove an operation-owned delete rejects a changed fingerprint without mutation: persist a deleting marker in the real journal, then request a reset-owned delete with a mismatched expected fingerprint; assert refusal, the bucket directory survives, and a re-assessment returns the original fingerprint.
- Prove a redirected bucket root is neither assessed nor deleted: symlink the secondary bucket root to external storage with a sentinel, assert both `assess_deletion` and `delete` refuse, and assert the symlink, external manifest, and sentinel survive byte-identical.
- Prove matching journal ownership and fingerprint permit the canonical hard erase, returning the reset operation id and observed fingerprint with the bucket directory gone.
- Prove absence requires journal proof: a missing bucket raises `ProfileNotFoundError`; an owned deleting marker for that bucket then makes the absence idempotently accepted (`already_absent`, no previous label).

## Outcome

Real-behavior throughout: real two-bucket runtime (`isolated_two_bucket_runtime`), real encrypted storage, real `ConfigResetJournalRepository`, real pointer/lock state, and a real symlink redirection — no mocks or monkeypatch. This suite is the executable proof that operation-owned deletion rejects mismatches and accepts only journal-proven absence, closing the campaign's dangling-pointer / retention-bypass safety defect at the deletion boundary. Full bucket_maintenance + config_reset suites green (86 tests); ruff clean; collection clean.

## Notes

Landed in commit `11356b4792`; re-verified at HEAD. The delete happy path clears the active-profile pointer before the reset-owned erase so the target is not the active bucket, matching the accepted phase order (strong logout / pointer clear precedes deletion). No skips, xfail, or tautological assertions.
