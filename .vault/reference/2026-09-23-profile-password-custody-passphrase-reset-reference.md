---
tags:
  - '#reference'
  - '#profile-password-custody'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:283e5222856bdd6554764e7349acdc2ceffc0f3b802c2db08863abda279fb845'
related:
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` reference: `Recovery passphrase reset as implemented`

How `config passphrase reset` behaves as shipped, read from the source on 2026-09-23 to ground the decision the custody decision had deferred: what a recovery-authorised passphrase replacement does to the profile lineage, the audit record, live sessions, the recovery record, archives and attempt throttling.

## Summary

### Path

The verb (`src/cadrumo/entrypoints/cli/config/_custody_command_specs.py:109-128`, handler `src/cadrumo/entrypoints/cli/config/passphrase.py:133`) resolves the target before reading any secret, then calls `reset_profile_passphrase_with_recovery` (`src/cadrumo/application/user_profile/recovery_custody.py:240`). That service checks confirmation and password policy first, unwraps the DEK with the recovery code, proves it against the sentinel, and hands it to `rewrap_profile_passphrase_under_lock` (`src/cadrumo/application/user_profile/passphrase_rotation.py:193`), the same second half an ordinary current-passphrase rotation uses.

### Lineage

- The re-minted envelope carries `password_generation = current + 1` (`passphrase_rotation.py:222`) and the held `dek_epoch` (`:220`).
- `previous_envelope_digest` is never set: neither the rewrap nor the adapter passes it (`src/cadrumo/adapters/persistence/storage/profile_custody.py:819-826`), so it defaults to `None` (`src/cadrumo/adapters/persistence/storage/custody/envelope.py:23`). Its only validation is digest format (`custody/records.py:141-147`); nothing reads it.
- Replace checks parse, `profile_id` and unchanged `dek_epoch` only (`custody/capsule.py:898-916`), then compare-and-swaps against the replaced envelope's digest (`profile_custody.py:948-953`). Generation monotonicity is not enforced at replace.

### Audit record

- A reset writes one `PROFILE_PASSPHRASE_ROTATED` event (`passphrase_rotation.py:248-251`; `src/cadrumo/domain/buckets/event.py:110,169`) whose payload is lineage only (`src/cadrumo/application/user_profile/capsule_record.py:637-645`), with the fixed actor `profile-capsule-lifecycle` (`capsule_record.py:47,650`).
- A recovery-authorised reset and a current-passphrase rotation are indistinguishable in every persisted record.
- `CUSTODY_PASSPHRASE_CHANGED`, `CUSTODY_RECOVERY_CODE_CREATED`, `CUSTODY_RECOVERY_CODE_ROTATED` and `CUSTODY_SECRET_STORE_RECOVERED` are declared (`event.py:221-224`) and emitted nowhere.

### Sessions

- Acceleration receipts bind `custody_generation` and `dek_epoch` into their AAD (`custody/acceleration_receipt_crypto.py:92-116`). Resume refuses a generation mismatch with `CUSTODY_CHANGED` and deletes the receipt (`custody/acceleration_receipt.py:855-865,893-899`), so a pre-reset receipt dies at its next resume; the reset itself deletes none.
- Record-session row provenance carries the envelope digest and generation (`capsule_record.py:198-228`), so a session opened before the reset cannot read the re-headed row.
- The login handover journal holds no custody field (`src/cadrumo/application/user_profile/login_handover.py:42-53`).
- No test covers a pre-reset receipt being refused.

### Recovery record

- Never rewritten by a reset (`capsule.py:910-916`); the wrapper binds only `(profile_id, dek_epoch)` (`profile_custody.py:902-908`), so the same code keeps working (`recovery_custody.py:254-255`; test `custody/tests/test_recovery_enrollment.py:332` resets twice with one code).
- `config profile recovery` has `enable`, `disable` and `status` (`src/cadrumo/entrypoints/cli/config/profile_command_specs.py:756-827`); enable refuses an existing wrapper (`recovery_custody.py:183-186`), so replacing a code is disable then enable.
- The reset result reports `recovery_enrollment_retained` (`passphrase.py:124-130`) but no text tells the operator the code remains valid.

### Archives

- An exported archive holds the full password envelope, sentinel, database, and an empty recovery slot (`src/cadrumo/application/user_profile/capsule_archive.py:130-171,217-245,281-288`).
- Restore (`src/cadrumo/entrypoints/cli/config/restore_cli.py:101-145` to `capsule_restore.py:169-216` to `lifecycle.py:97-158`) unlocks with the archive's own envelope and checks UUID, digests, epoch and sentinel only (`lifecycle.py:126-144`); it never compares generations with a live profile. It cannot overwrite a live profile of the same UUID (`custody/_capsule_filesystem.py:109-110,158-159`), but after deletion a pre-reset archive restores the old passphrase, without recovery, with no warning.
- Because the DEK epoch is held, every archive and copy made before the reset remains decryptable by the passphrase it was made under.

### Throttling

- Reset does not use the per-profile login throttle (`login_session.py` lines 360, 934-950, 1042-1068, 1100 are its only callers); a wrong code is refused but not counted (`recovery_custody.py:286-297`).

### Existing tests

`custody/tests/test_recovery_enrollment.py:214,283,332,353,379,399,439`; `custody/tests/test_custody_isolation_matrix.py:86`; `custody/tests/test_authentication_failure_mapping.py:44,56`; `src/cadrumo/entrypoints/cli/config/tests/test_profile_recovery_cli.py:399-518`; `test_passphrase_command_spec.py:23,75,99`. None covers restore after a reset, the reset's audit record, or pre-reset receipt refusal.
