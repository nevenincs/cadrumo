---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a50517f3356a4615b7facc7c56f854db9bf6e410d52944eaa9fcfd315b4ad9af'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# `current-schema-only-purge` ledger

## Changes

- `S01` `T` `src/cadrumo/domain/user_profile/_values.py`
- `S02` `T` `src/cadrumo/application/user_profile/_lifecycle.py`
- `S03` `T` `src/cadrumo/domain/user_profile/tests/test_payload_schema_identity.py`
- `S04` `T` `src/cadrumo/core/_bucket_pointer.py`
- `S05` `T` `src/cadrumo/core/tests/test_bucket_pointer.py`
- `S06` `T` `src/cadrumo/domain/invoices/_models.py`
- `S07` `T` `src/cadrumo/domain/invoices/tests/test_catalogue.py`
- `S08` `T` `src/cadrumo/adapters/persistence/storage/envelope/_envelope.py`
- `S09` `T` `src/cadrumo/adapters/persistence/storage/envelope/tests/test_cipher_envelope_version_gate.py`
- `S10` `T` `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`
- `S11` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`
- `S12` `T` `src/cadrumo/application/user_profile/_bundle_encryption.py`
- `S13` `T` `src/cadrumo/application/user_profile/tests/test_bundle_export.py`
- `S14` `T` `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`
- `S15` `T` `src/cadrumo/adapters/persistence/storage/secret_store/tests/test_secret_index_version_gate.py`
- `S16` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`
- `S17` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `S17` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`
- `S17` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_kdf_salt.py`
- `S17` `T` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_master_key_file_fallback.py`
- `S21` `T` `src/cadrumo/application/calculations/_observations_repository.py`
- `S22` `T` `src/cadrumo/application/modelo/_revision_persistence.py`
- `S23` `T` `src/cadrumo/application/calculations/tests/test_m303_carry_ingress.py`
- `S24` `T` `src/cadrumo/application/user_profile/_repository.py`
- `S25` `T` `src/cadrumo/application/user_profile/_bundle_encryption.py`
- `S25` `T` `src/cadrumo/adapters/persistence/storage/__init__.py`
- `S26` `T` `src/cadrumo/adapters/persistence/storage/master_key/_master_key_records.py`
- `S28` `T` `src/cadrumo/application/calculations/_m303_carry_ingress.py`
- `S29` `T` `src/cadrumo/application/modelo/_iva_wallet_gate.py`
- `S29` `T` `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py`
- `S29` `T` `src/cadrumo/application/modelo/tests/test_local_cross_period_carry.py`
- `S32` `T`
- `S33` `T`
- `S35` `T` `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py`
- `S35` `T` `src/cadrumo/application/calculations/tests/test_iva_wallet_reconciliation.py`
- `S37` `T` `src/cadrumo/domain/censo/_certificado.py`
- `S37` `T` `src/cadrumo/adapters/inbound/censo/_parser.py`
