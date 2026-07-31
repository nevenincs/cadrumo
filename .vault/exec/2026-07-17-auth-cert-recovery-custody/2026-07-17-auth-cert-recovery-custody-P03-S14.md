---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:9f83e9e35c4add8f0d468c4e6832da4e94f37973409c96530dfe49b9e9eae2d5'
step_id: 'S14'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Preserve the prior recovery envelope until a candidate mnemonic has been fully verified

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`

## Description

- Add `atomically_install_verified_recovery` to the recovery primitives module: run a caller-supplied verification callback and write the payload through the atomic secure writer only once that callback returns without raising.
- Wire the facade create and rotate flow to install the staged candidate exclusively through this primitive, with a verification closure that fully unwraps the candidate under the operator's retype.

## Outcome

The prior recovery envelope survives until a candidate mnemonic is fully verified. Because the atomic write is unreachable until verification passes, a cancelled, mistyped, or corrupt candidate leaves any existing envelope untouched, and the replacement is all-or-nothing.

Evidence attributed at HEAD. Commit `b1d80821c9` (2026-07-17) adds 36 lines to `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`. At HEAD that module defines `atomically_install_verified_recovery`, whose body calls `verify()` first and only then reaches `atomic_write_secure_bytes`; the ordering is structural rather than conditional, so there is no path that writes before verifying. In `_recovery_facade.py` the `_enroll_recovery` helper builds a `_verify_candidate` closure that calls `verify_recovery_mnemonic` against the retyped mnemonic and raises `RecoveryVerificationError` on mismatch, then passes it to the primitive as the sole install path; no other write call reaches the envelope path in that module. The contract is covered from both sides. `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py` carries `test_rotate_preserves_prior_envelope_on_failed_confirmation`, `test_rotate_preserves_prior_envelope_on_cancelled_confirmation`, and `test_create_writes_no_envelope_on_failed_confirmation`; `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py` carries the `TestInstallAfterVerification` class covering install-on-pass, prior-file-survives, and no-file-written-on-empty-store. Both files pass, at 25 and 26 collected tests respectively.

## Notes

Documentation reconciliation only; the step was not re-executed. The originating record `S73` carries an identical heading and identical scope file, so the map to `S14` is exact.

The primitive is deliberately shape-agnostic — payload bytes plus a verify callback — so it lives in the low-level primitives module without importing the higher-level envelope record and without creating an import cycle with the facade. That design choice is visible at HEAD in the deferred function-local import of `atomic_write_secure_bytes`.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

No substantiation gap for this step.
