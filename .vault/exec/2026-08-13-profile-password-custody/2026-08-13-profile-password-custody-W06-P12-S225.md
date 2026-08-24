---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e610edd2f9587144baed2034480760642522a139fe8cae905c9c18bf959f50ce'
step_id: 'S225'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Replace the capsule-source symlink platform skip with a deterministic real-filesystem reparse-point-or-directory refusal witness while retaining linked-content non-adoption where symlinks are supported

## Scope

- `src/cadrumo/application/user_profile/tests/test_capsule_source_reads_are_anchored.py`

## Description

- Replace the platform-dependent symlink prerequisite with a deterministic real-filesystem reparse-point-or-directory witness.
- Exercise real linked-content non-adoption whenever symlink construction succeeds, and fall back to a real directory at the exact capsule-member path otherwise.
- State explicitly that the fallback proves non-regular-file refusal rather than link traversal.
- Run the focused anchored-source module, global no-skip/xfail ratchet, Ruff, ty, and independent safety review.

## Outcome

The final anchored-source module passed all 3 tests natively in 1.12 seconds and all 3 under WSL/POSIX in 8.06 seconds. The global no-skip/xfail ratchet passed all 25 tests in 44.88 seconds. Ruff and ty passed for the modified module.

The witness now reaches the production anchored reader on every filesystem without a skip. A supported symlink keeps the original exfiltration-shaped proof and verifies that linked payload text does not reach the refusal. A filesystem that refuses symlink creation receives a real directory at the same envelope-member path and proves the production reader rejects that non-regular member; the test does not claim that branch covers linked-content traversal.

## Notes

No production code, fake filesystem, mock, stub, skip, xfail, or platform marker was added. A concurrent earlier commit had removed the explicit `pytest.skip`, but still made successful symlink construction a prerequisite; this Step closes the remaining deterministic cross-platform evidence gap. Independent review initially found the Windows diagnostic assertion was too narrow for POSIX `O_NOFOLLOW`, which securely reports the linked leaf as unavailable. The final assertion accepts those two observed refusal forms while retaining the linked-payload non-disclosure check.
