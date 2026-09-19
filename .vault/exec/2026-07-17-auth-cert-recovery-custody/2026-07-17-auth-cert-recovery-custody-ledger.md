---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9532e163fe90d04d86df7b325af220cb45ed6b6d17cb49526b994441ef3399ac'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# `auth-cert-recovery-custody` ledger

## Changes

- `S01` `T` `src/cadrumo/application/auth/_operator.py`
- `S02` `T` `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
- `S03` `T` `src/cadrumo/application/auth/tests/test_operator.py`
- `S04` `T` `src/cadrumo/application/auth/tests/test_sessions_storage_state_paths.py`
- `S05` `T` `src/cadrumo/application/auth/tests/test_acquisition_lock.py`
- `S06` `T` `src/cadrumo/application/auth/_certificate_secret_backend.py`
- `S07` `T` `src/cadrumo/application/auth/_certificate_sources_operator.py`
- `S08` `T` `src/cadrumo/application/auth/_certificate_sources.py`
- `S09` `T` `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`
- `S10` `T` `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py`
- `S11` `T` `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`
- `S12` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`
- `S13` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`
- `S14` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`
- `S15` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`
- `S16` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`
- `S17` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery_facade.py`
- `S18` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`
- `S19` `T` `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py`
- `S20` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_passphrase_failclosed.py`
- `S21` `T` `src/cadrumo/adapters/persistence/storage/master_key/__init__.py`
- `S22` `T` `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`
- `S23` `T` `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`
- `S24` `T` `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`
- `S25` `T` `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`
- `S26` `T` `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `S27` `T` `src/cadrumo/entrypoints/cli/_config/tests/test_config.py`
- `S28` `T` `src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py`
- `S29` `T` `src/cadrumo/entrypoints/cli/tests/test_help_without_secrets.py`
- `S30` `T` `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`
- `S31` `T` `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`
- `S32` `T` `src/cadrumo/entrypoints/cli/_config/_certificate.py`
- `S33` `T` `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`
- `S34` `T` `src/cadrumo/entrypoints/cli/tests/test_destructive_verbs_require_yes.py`
- `S35` `T` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `S36` `T` `src/cadrumo/application/operator_surface/_help.py`
- `S37` `T` `src/cadrumo/locales/en.yml`
- `S38` `T` `src/cadrumo/agent/`
- `S39` `T` `docs/how-to/authenticate-with-aeat.md`
- `S40` `T` `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`
- `S41` `T` `delete override_secret_store`
- `S41` `T` `the module-global _override_store`
- `S41` `T` `its if-override branch`
- `S41` `T` `and both blob_store and storage __init__ facade exports`
- `S41` `T` `migrate the four consuming tests to pass an EphemeralMasterKeyProvider-backed SecretStore explicitly`
- `S41` `T` `in one atomic relocation commit including apidocs scaffold`
- `S41` `T` `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`
- `S42` `T` `src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py`
- `S43` `T` `src/cadrumo/adapters/persistence/storage/__init__.py`
- `S44` `T` `src/cadrumo/entrypoints/cli/_config/_certificate.py`
- `S45` `T` `.vault/audit`
- `S46` `T` `src/cadrumo/entrypoints/cli/_config/_secure_input.py`
- `S47` `T` `src/cadrumo/application/user_profile/_custody.py`
- `S48` `T` `src/cadrumo/entrypoints/cli/_config/_secure_input.py`
- `S49` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`
- `S50` `T` `src/cadrumo/application/user_profile/_custody.py`
- `S51` `T` `src/cadrumo/application/user_profile/_custody.py`
- `S52` `T` `src/cadrumo/entrypoints/cli/_config/_secure_input.py`
- `S53` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key_io.py`
- `S54` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`
- `S55` `T` `src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py`
- `S56` `T` `src/cadrumo/application/user_profile/_login_session.py`
