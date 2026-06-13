---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P03.S03'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P03.S03

Implement AES-256-GCM wrap/unwrap of the per-bucket data-encryption key at
`src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py` per ADR-1
section 3. The wrap binds to the bucket id via AEAD AAD so a wrapped
DEK cannot be silently swapped under another bucket's manifest.

- Created: `src/aeat/adapters/persistence/storage/master_key/_dek_wrap.py`
- Created: `src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py`

## Description

`wrap_dek(*, kek, dek, bucket_id)` mints a fresh 12-byte nonce per
call, runs `AESGCM(kek).encrypt(nonce, dek, aad)` where
`aad = b"aeat.dek-wrap.v1:" + bucket_id`, and splits the resulting
ciphertext-with-tag into a 32-byte ciphertext + 16-byte tag carried by
the frozen `WrappedDek` pydantic v2 record.

`unwrap_dek(*, kek, wrapped, bucket_id)` reconstructs the wire shape
and runs `AESGCM(kek).decrypt(...)`; AEAD failure surfaces as the
upstream `cryptography.exceptions.InvalidTag` which the caller
translates to a typed error at its boundary (the CLI verb layer in P05
maps it onto `MasterKeyPassphraseMismatchError` or equivalent).

The wire-shape choice is deliberate: storing `ciphertext` and `tag`
separately on `WrappedDek` (rather than the concatenated `cipher+tag`
shape used by the substrate's bulk `EncryptedBlob` record) matches the
ADR-1 section 3 wire description "nonce (12 bytes), ciphertext (32
bytes), tag (16 bytes)".

## Tests

`test_dek_wrap.py` (11 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- Known-answer: `unwrap_dek` recovers the reference DEK from a
  ciphertext captured via a one-time direct `AESGCM.encrypt` call under
  documented inputs. The expected hex
  `544545e66d237ace67966d425b8df6ee9c83200606732831f8a2fc5fa41c5a0c`
  + `ae235f7967e573c9a93eee2e98ab458d` is upstream-library output, NOT a
  re-run of `wrap_dek` against itself.
- Random-nonce round-trip: `unwrap_dek(wrap_dek(dek)) == dek`.
- Two consecutive wraps under the same KEK produce different nonces
  AND different ciphertexts (nonce-misuse regression guard).
- Wrong KEK fails the AEAD tag check.
- Wrong bucket id (AAD mismatch) fails the AEAD tag check.
- Single-bit tamper of the tag fails the AEAD tag check.
- Single-bit tamper of the ciphertext fails the AEAD tag check.
- Wrong-size KEK / DEK / empty bucket id all fail closed at the
  argument validation layer.
- `WrappedDek` strict-validation rejects mismatched field lengths
  (nonce != 12, ciphertext != 32, tag != 16).

`uv run pytest src/aeat/adapters/persistence/storage/master_key/test_dek_wrap.py -x -q` :
11 passed.

`uv run ruff check` clean.
