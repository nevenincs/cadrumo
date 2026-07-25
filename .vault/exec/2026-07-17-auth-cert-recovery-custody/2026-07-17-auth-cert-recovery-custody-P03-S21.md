---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S21'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Re-export only the explicit passphrase and recovery lifecycle operations

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`

## Description

- Re-export the explicit recovery lifecycle operations through the master-key package facade: `recovery_status`, `recovery_create`, `recovery_rotate`, `recovery_verify`, and `recovery_recover`.
- Re-export their result records: `RecoveryEnrollmentMode`, `RecoveryLifecycleStatus`, `RecoveryEnrollmentOutcome`, `RecoveryVerifyOutcome`, and `RecoveryRecoverOutcome`.
- Keep the internal helpers, the verified-install primitive and the custody guard, unexported.

## Outcome

The package facade exposes the recovery lifecycle as its public surface, so cross-package consumers import the operations from the master-key package top level without reaching into private modules.

Evidence attributed at HEAD. Commit `b1d80821c9` (2026-07-17) adds 20 lines to `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`. At HEAD that module both imports and lists in `__all__` all five operations and all five result records, so the export is real rather than an import that never reached the public tuple — a distinction worth checking separately, since an import alone would not satisfy the project's facade rule.

The negative half of the step was verified as deliberately as the positive half. `atomically_install_verified_recovery` appears nowhere in the facade module, neither imported nor exported, and the custody guard `_require_file_custody` is likewise absent; both remain private to their defining modules. This matters because the step's wording is "re-export **only** the explicit lifecycle operations", and a record that confirmed only the presence of the ten public names would not have tested that word.

## Notes

Documentation reconciliation only; the step was not re-executed. The originating record `S80` carries an identical heading and identical scope file, so the map to `S21` is exact.

One honest qualification on the word "only". The originating record states that the pre-existing low-level recovery primitives stayed exported to keep the then-current application custody module compiling, with that module and the CLI migrated onto the lifecycle operations in a later wave. At HEAD the facade module `_recovery_facade.py` still exports lower-level names alongside the five operations, including the envelope load and save helpers, the mint and unwrap helpers, and the mnemonic verify helper. So "only" is true of the *lifecycle* surface — no internal helper leaked into the public facade — but it is not true in the stronger sense that the low-level primitives were withdrawn at this step. A reader auditing whether those primitives were later retired must look to the P04 door and its migration, not to this record.

This step's target file has been touched by four subsequent commits belonging to the later profile-login and persisted-session work. Those commits changed neighbouring exports in the same facade and did not remove any of the ten recovery names, which were confirmed present at HEAD after that churn rather than only as of the attributing commit.

The `date` frontmatter is deliberately the landing date `2026-07-17`, not the reconciliation date `2026-07-25`.

Substantiation is complete for the ten exports and for the unexported internal helpers, with the "only" qualification recorded above.
