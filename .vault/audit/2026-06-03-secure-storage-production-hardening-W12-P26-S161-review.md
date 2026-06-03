---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S161]]'
---

# `secure-storage-production-hardening` `W12.P26.S161` Review

## S161-001 | PASS | Bucket manifest remains plaintext metadata

`src/aeat/adapters/persistence/storage/bucket/_manifest.py` defines strict pydantic records for bucket manifest metadata: bucket identity, label, UTC timestamps, KDF parameters, public Argon2id salt, recovery enrollment state, idle-lock settings, key schedule, schema version, and lifecycle status.

The file does not persist a passphrase, derived key, wrapped DEK, decrypted DEK, recovery secret, taxpayer payload, ledger row, modelo export body, or secure-object ciphertext. The `master-key` signal is accepted because the manifest carries the public KDF and schedule metadata needed to resolve the separate master-key surface, not the master key itself.

## S161-002 | PASS | Plaintext lifecycle mirror is bounded and fail-closed

`BucketLifecycleStatus` is a plaintext mirror used for manifest discovery so tombstoned buckets can be filtered without decrypting the user profile. The field is required with no default, which keeps missing lifecycle state fail-closed instead of silently rehydrating a deleted profile as active.

The enum values intentionally mirror the domain lifecycle status string values. That duplication is a boundary mapping contract rather than a new lifecycle authority; the encrypted profile remains authoritative and repository writes are responsible for keeping both records in lockstep.

## S161-003 | PASS | Validation conventions and tests are acceptable for this boundary

The `ValueError` raises are pydantic field-validator signals, not user-facing application exceptions. No direct environment access, local settings construction, broad exception catch, suppression, fake, stub, monkeypatch, skip, or xfail markers were found in the reviewed implementation or target tests.

The tests exercise strict pydantic validation and real TOML filesystem roundtrips. The roundtrip fixture uses non-default lifecycle state and mutates persisted TOML to prove the status field is not tautologically flattened or defaulted.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/bucket/test_manifest.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py` passed with 16 tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/bucket/_manifest.py src/aeat/adapters/persistence/storage/bucket/test_manifest.py src/aeat/adapters/persistence/storage/bucket/test_manifest_roundtrip.py` passed.
- Touched-file hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access. Its only hit was a test module docstring stating that the roundtrip test uses real filesystem I/O and no mocks.

Review-agent note: spawning `vaultspec-code-reviewer` for this row failed with the current agent thread limit, so the formal review was completed locally using the same checklist.

Disposition: close `AFR-059` as `remote-mirror` metadata.
