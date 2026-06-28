---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S81'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S81 Master Key Storage Decomposition

Scope: decompose master key storage adapter by derivation, rotation, and persistence concerns behind the storage facade.

## Description

- Extract Argon2id derivation constants and helpers into `src/aeat/adapters/persistence/storage/master_key/_master_key_derivation.py`.
- Extract persisted envelope, KDF, and wrapped bucket-DEK pydantic records into `src/aeat/adapters/persistence/storage/master_key/_master_key_records.py`.
- Extract passphrase input, base64, secure atomic write, and file-mode helpers into `src/aeat/adapters/persistence/storage/master_key/_master_key_io.py`.
- Extract ephemeral provider state into `src/aeat/adapters/persistence/storage/master_key/_master_key_ephemeral.py`.
- Extract bucket-DEK activation, wrapping document IO, idle-window resolution, and bootstrap minting into `src/aeat/adapters/persistence/storage/master_key/_master_key_bucket_dek.py`.
- Extract the unsecured-backend synthetic tax-id allow-list and real tax-id classifier into `src/aeat/adapters/persistence/storage/master_key/_master_key_tax_id.py`.
- Keep provider orchestration and the public master-key package facade stable through `src/aeat/adapters/persistence/storage/master_key/_master_key.py` and `src/aeat/adapters/persistence/storage/master_key/__init__.py`.
- Preserve persisted KDF parameter authority by delegating explicit on-disk Argon2id parameters to the new derivation helper.
- Align storage tests and guards with existing decompositions: real master-key AST path, current central unlock remediation, storage package smoke import target, and reviewed sensitive write inventory entries.

## Outcome

Master-key document records, KDF derivation logic, IO helpers, ephemeral provider state, bucket-DEK activation, and tax-id canary logic are separated from provider orchestration while preserving package-level consumer imports and persisted KDF semantics. `src/aeat/adapters/persistence/storage/master_key/_master_key.py` now stays below the hard 1250-line module budget at 1241 lines.

## Notes

The combined storage test run initially surfaced stale contract paths after helper extraction. The reviewed write inventory and package-smoke import target were updated to the decomposed source paths before verification.
