---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S457'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P40.S457 - Implement first-class config custody verbs

Scope: implement first-class config custody verbs for lock, unlock, rekey,
recover, show-recovery, and verify-recovery using the accepted recovery facade,
profile lifecycle session path, and locale-backed CLI copy.

## Description

- Routed `config lock` and `config unlock` through the canonical profile
  lifecycle session path and active-profile pointer handling.
- Added `config rekey`, `config recover`, `config show-recovery`, and
  `config verify-recovery` under the config CLI root.
- Added typed CLI payload schemas for the six custody verbs and enrolled them
  in the command envelope registry.
- Replaced the application custody recovery path with the typed
  `RecoveryRecord` facade: `mint_recovery_envelope`, `save_recovery_envelope`,
  `load_recovery_envelope`, `verify_recovery_mnemonic`, and
  `unwrap_recovery_envelope`.
- Promoted the typed recovery facade and recovery verification error through
  public storage exports so application code does not reach into private
  substrate modules.
- Added real subprocess CLI coverage for recovery enrollment, recovery
  verification success and failure, passphrase rekey, recovery rebind, and typed
  recovery-envelope persistence.
- Mirrored recovery enrollment into the active profile manifest so the
  plaintext bucket status cannot drift from the persisted recovery envelope.
- Added internal bucket-session activation spans to recovery enrollment,
  passphrase rekey, and recovery rebind so the root-exempt custody verbs still
  prove the active bucket lifecycle where the operation depends on the current or
  recovered secret store. `verify-recovery` intentionally remains independent of
  the current passphrase.
- Added `config recover`, `config rekey`, `config show-recovery`, and
  `config verify-recovery` repair policy rows and command-surface coverage for
  the nested custody registration module.

## Outcome

The first-class config custody verbs are implemented and verified against the
file secret-store backend. Recovery enrollment persists a typed
`RecoveryRecord` envelope and does not persist the plaintext mnemonic; recovery
verification and recovery rebind consume the same accepted facade.
Root bootstrap exemptions remain necessary for these verbs, but the custody
service now owns the bucket-session proof inside operations that need an active
or recovered secret store.

Validation:

- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/tests/test_recovery_facade.py src/aeat/adapters/persistence/storage/master_key/tests/test_recovery_record.py -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py -m integration -q`
- `uv run --no-sync python -m aeat.locales audit`
- `uv run --no-sync ruff check src/aeat/application/user_profile/_custody.py src/aeat/application/user_profile/__init__.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/master_key/__init__.py src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/entrypoints/cli/_bootstrap_exempt.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/_custody.py src/aeat/entrypoints/cli/_config_payloads.py src/aeat/application/repair_integrity.py src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/tests/test_repair_policy_coverage.py`
- `uv run --no-sync aeat config lock --help`
- `uv run --no-sync aeat config unlock --help`
- `uv run --no-sync aeat config rekey --help`
- `uv run --no-sync aeat config recover --help`
- `uv run --no-sync aeat config show-recovery --help`
- `uv run --no-sync aeat config verify-recovery --help`

## Notes

A concurrent secure-object change left `json.dumps` in revision metadata without
the standard-library `json` import. The custody CLI gate exposed the regression
during profile creation, and this step restored the missing import because it
blocked the verified backend path for S457.
