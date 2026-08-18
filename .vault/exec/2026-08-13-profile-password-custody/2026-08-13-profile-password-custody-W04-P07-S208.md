---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:e0366f25436e8d778271922559d81cb596998adbfb714092e641e8e84e95e262'
step_id: 'S208'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh delete the verified-dead custody surfaces the cutover left behind — the orphaned zeroise husk module with no importer anywhere in the tree, the dead transient-bucket-file helper, and the unreached rename-label application methods whose CLI door is deliberately retired — re-documenting the surviving deletion-paths module under its true name, purging the stale compiled artefacts whose sources were deleted, and restoring lane reachability for the custody keychain tests stranded by the session relocation

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_io.py and src/cadrumo/adapters/persistence/storage/ and src/cadrumo/application/bucket_maintenance/_manifest_digest.py and src/cadrumo/application/user_profile/ and src/cadrumo/domain/user_profile/_protocols.py and justfile`

## Description

- Re-document the surviving deletion-path module under its true name: replace
  the manifest-digest docstring of `_deletion_paths.py` with its real
  deletion-path validation contract, drop the dead
  `_is_transient_bucket_file` helper, and point the service import, the
  `.importlinter` contract and its ledger test, and the scaffolded API
  reference at the module's actual name.
- Delete the unreached `rename_label` methods — the custody transaction
  capability method, the `ProfileCapsuleLifecycle` wrapper, the
  `_label_authority` attribute, and the `ProfileCustodyLabelAuthorityProtocol`
  export — reworking the two label-provenance tests that exercised them onto
  the surviving create-time and refusal invariants, and perturbing the label
  record directly in the delete-while-logged-in marker test.
- Keep the `DECLARED_UNIMPLEMENTED_SURFACES` rename declaration and its held
  payload classes intact, rewording the note to record the removal rather
  than the live method.
- Purge the stale `__pycache__` trees under the touched packages.
- Confirm the `test-os-keychain` lane already names
  `src/cadrumo/adapters/persistence/storage/custody/tests` at HEAD, and clear
  a stale staged removal from the shared index so lane reachability stays
  intact.
- Run the gates: ruff, the targeted custody/importlinter pytest batch,
  lane-reachability, collect-only, and the apidocs scaffold check.

## Outcome

The verified-dead surfaces are gone: the orphaned master-key IO husk stub, the
dead transient-bucket-file helper, and every unreached `rename_label` method
and its domain protocol member. The surviving deletion-path module carries its
true name end to end — source, import contracts, and API reference agree — and
the operator-facing schema declaration preserves the deliberate retirement
evidence. Ruff, collect-only, and the scaffold check are green; the targeted
pytest batch and lane-reachability fail only on drift already present at HEAD
(details in Notes).

## Notes

- Executor split: the code edits were applied by an earlier executor run that
  died on context exhaustion; this run performed the diff review, gate runs,
  index repair, commit, and record.
- Commit `476078efa0` carries the code sweep; the `justfile` lane fix already
  landed at HEAD as `9c3e0fc448`, so no `justfile` hunk was committed here and
  the peer's unrelated working-tree hunks were left untouched.
- Pre-existing failures, verified identical at HEAD, reported verbatim:
  importlinter drift naming `tui.launcher` ignore entries and an unreconciled
  `_custody_transactions` edge plus stale reconciled sources; the
  bucket-maintenance browse/disk-usage fixtures broken by the UUID-requiring
  capsule harness from commit `58cd742301`; the assess-deletion
  DID-NOT-RAISE refusal with the service untouched since `350de5347b`; and the
  nine unreachable `dev/ci` and `dev/packaging` tests from the peer's
  in-flight dev-test relocation.
