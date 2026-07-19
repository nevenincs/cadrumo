---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Invoke target-scoped auth reset and delete canonical secure-storage certificate secrets before each target deletion without certificate keyring reconciliation or migration

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Clear target-scoped auth before each target's deletion (`_clear_auth_for_targets`): record the `AUTH_CLEARING` phase and persist, call `reset_operator_auth(all_providers=True, target_bucket_id=target.bucket_id)`, then record `AUTH_CLEARED`.
- Delete each target's canonical secure-storage certificate secrets via that same `reset_operator_auth` call, which owns provider config, sessions, acquisition locks, registered certificate sources, and their bound secrets — no certificate keyring reconciliation, migration, or fallback participates.
- Re-read the deletion fingerprint and retention decision after auth clearing (the auth reset changes on-disk bucket bytes) so the later delete verifies against the post-auth-clear fingerprint, refusing if the target vanished mid-cleanup.

## Outcome

Auth state and certificate secrets are erased while each target is still reachable, before the bucket is removed, matching the ADR's ordered phase 3. The re-read fingerprint keeps the deletion-boundary safety check honest across the auth-clearing mutation. Proven by the P03.S15 test (a registered certificate source with a secret blob is erased — `secret_blob_root` is empty after reset — and the acquisition lock is cleared). 19 P03 tests green.

## Notes

Landed in commit `60135859e2`; re-verified at HEAD. `reset_operator_auth` lives in `application/auth/**` (a peer's cutover surface); this phase only CALLS it through the package facade and does not edit it, honouring the scope boundary. The deleted certificate keyring backend has no participation, per the governing ADR's no-legacy hard cut.
