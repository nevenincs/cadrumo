---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1efc3c0e56b5af74fdd813f11124847fa3177f5a05471f39716c10b846fefa53'
step_id: 'S218'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Confirm recovery artifacts remain external restore proofs only, remove any API or prose that permits later enrollment or treats a missing creation wrapper as current-format success, and retain password login without recovery reads

## Scope

- `src/cadrumo/application/user_profile/_recovery_custody.py and src/cadrumo/application/user_profile/_capsule_restore.py and src/cadrumo/application/user_profile/_custody_ports.py and src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Make the normal archive recovery slot permanently empty and reject non-empty recovery cargo.
- Remove recovery reads from the shared capsule-source reader and recovery installation from both restore authorities.
- Require creation callers to supply recovery while removing the restore-time recovery writer.
- Replace the ambiguous enrollment facade with an explicitly creation-only minting door.
- Prove real password login succeeds with missing and malformed recovery material.
- Migrate direct lifecycle test publishers through a secret-wiping creation fixture.

## Outcome

- Normal backup and password restore do not parse recovery; damaged recovery cannot block either operation.
- Recovery artifacts remain identity-bound proof for explicit artifact restore and never become enrolled recovery in the destination.
- `ProfileCapsuleLifecycle.create` has no password-only signature and `restore` has no recovery-envelope argument.
- The old public `enroll_profile_recovery` and raw material-construction facade exports are gone; the remaining public mint is named and documented for creation only.
- Core application, storage, lifecycle, isolation, archive, restore, login-independence, and TUI reachability suites passed 56 tests. Ancillary migrated fixture suites passed 28 relevant tests; two unrelated operator-output schema failures remain characterized.
- Scoped Ruff passed outside an unrelated concurrently edited facade file; scoped ty passed for the production boundary and new login proof.

## Notes

- Formal review initially found that the shared source reader still parsed recovery and that lower lifecycle signatures retained forbidden optional/installing paths. Both findings were corrected before close.
- Two pre-existing operator-output capability/schema assertions fail independently of custody and were not changed.
- The shared worktree contains concurrent edits in the application facade and several migrated fixture files; only S218 hunks are intended for capture.
