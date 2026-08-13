---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:09d8fdb42f02b34b609aad2614d75c28d8ee8ee6c584a3f9e79748ff1d50d3c4'
step_id: 'S21'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# verify encrypted `Justificante` persistence at its canonical adapter boundary and remove the obsolete domain duplicate

## Scope

- `src/cadrumo/adapters/persistence/profile/tests/test_justificante_secure_storage_roundtrip.py`
- `src/cadrumo/domain/justificante/tests/test_secure_storage_roundtrip.py` (deleted)

## Description

- The canonical test is owned by the profile persistence adapter, beside
  `JustificanteRepository`, rather than by the `justificante` domain. It drives
  the production repository through the active runtime profile, encrypted SQL
  object store, and SQLite engine.
- Its populated fixture carries non-default values for the receipt's optional
  fields and asserts strict Pydantic equality after the encrypted save/load
  cycle. Focused field witnesses retain signal for the URL, path, monetary
  `Decimal` values, and presentation id.
- The refusal proof rewrites only the encrypted envelope payload's CSV to the
  shape-valid foreign canonical CSV `ZXCV1234QWER5678`. The row remains filed
  under the original CSV, so loading it proves natural-key identity binding:
  the payload decrypts and validates, but `SecureObjectRowIdentityError`
  exposes the expected and payload identifiers instead of returning a foreign
  receipt.
- Both runtime setup and encrypted-payload mutation use the shared
  `cadrumo.tests.secure_sql` helpers (`isolated_runtime_profile` and
  `mutate_encrypted_secure_object_json`), removing the local SQL/crypto
  manipulation that had duplicated this boundary exercise in the domain suite.
  The shared mutation helper now has 25 test-module callers, including the
  notification-document custody suite migrated from its duplicate mechanical
  decrypt/JSON/mutate/encrypt helper.
- Delete the obsolete parallel domain suite. Persistence behaviour belongs to
  the adapter test; the remaining domain tests cover the receipt vocabulary,
  CSV bound, and filing-target contract.

## Outcome

The canonical adapter suite contains the strict encrypted roundtrip and the
shape-valid foreign-CSV refusal. It is the sole owner of this persistence
contract; the duplicate domain suite is absent.

## Validation

- `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/profile/tests/test_justificante_secure_storage_roundtrip.py`
- `uv run --no-sync pytest -q src/cadrumo/domain/justificante/tests`
- `uv run --no-sync ruff check src/cadrumo/adapters/persistence/profile/tests/test_justificante_secure_storage_roundtrip.py`
- `uv run --no-sync ty check src/cadrumo/adapters/persistence/profile/tests/test_justificante_secure_storage_roundtrip.py`
- `git diff --check -- src/cadrumo/domain/justificante/tests/test_secure_storage_roundtrip.py .vault/exec/2026-08-07-canonical-identifiers/2026-08-07-canonical-identifiers-W02-P03-S21.md`
