---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P03.S02'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P03.S02

Implement the Argon2id KEK derivation helper at
`src/aeat/adapters/persistence/storage/master_key/_kdf.py` per ADR-1
section 1. The helper is a thin typed wrapper around `argon2-cffi`'s
`hash_secret_raw` that consumes the manifest-side `KdfParams` record
(P01.S01) and produces a 32-byte KEK. No caches, no module-global state.

- Created: `src/aeat/adapters/persistence/storage/master_key/_kdf.py`
- Created: `src/aeat/adapters/persistence/storage/master_key/test_kdf.py`

## Description

`derive_kek(passphrase, kdf_params)` reads the algorithm tag, cost
parameters, salt, and requested output length from the manifest-side
record (so a bucket enrolled under an older parameter set still
unlocks; only `aeat config rekey` rebinds the bucket to the canonical
OWASP-2024 numbers). The helper refuses any algorithm other than
`argon2id` and any `output_length` other than 32 bytes; both rejections
are fail-closed.

The inline `_derive_kek` and `_derive_kek_with_params` helpers at
`src/aeat/adapters/persistence/storage/master_key/_master_key.py` lines
203 - 218 and 771 - 781 will route through this module once the
`_master_key.py` legacy providers are rewritten under the
`BucketSession` pipeline (lands in P03.S07 and the P05 CLI wiring); this
step ships the helper as the canonical home so downstream steps consume
a single derivation surface.

## Tests

`test_kdf.py` (6 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- Known-answer: `derive_kek(b"correct horse battery staple", canonical_params)`
  produces the upstream `argon2-cffi` reference output captured at test
  authoring time. The expected hex
  `bcaf6fd0e5aaa31b272240c38067653313e9f7802fc226ccf8416cf7bcf9e644`
  comes from a one-time direct invocation of
  `argon2.low_level.hash_secret_raw` (documented in the test module's
  docstring), NOT from a re-run of `derive_kek` against itself.
- Output is 32 bytes for arbitrary salt/passphrase.
- Different salts produce different KEKs.
- Different passphrases produce different KEKs.
- Non-`argon2id` algorithm fails closed.
- Non-32 `output_length` fails closed.

`uv run pytest src/aeat/adapters/persistence/storage/master_key/test_kdf.py -x -q` :
6 passed.

`uv run ruff check` clean.
