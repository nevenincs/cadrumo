---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P03.S04'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P03.S04

Wire the existing BIP-39 mnemonic + HKDF-derived recovery KEK + AES-256-GCM
primitives in `_recovery.py` through a typed facade consuming the
`RecoveryRecord` envelope (P01.S03) and the `BucketSession` (P03.S01) per
ADR-1 section 4. The internals of `_recovery.py` are unchanged; only the
boundary is rewritten.

- Created: `src/aeat/adapters/persistence/storage/master_key/_recovery_facade.py`
- Created: `src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py`

## Description

The facade exposes four typed entry points:

- `mint_recovery_envelope(*, dek, created_at)` mints a fresh 24-word
  mnemonic via `generate_recovery_key`, wraps the supplied DEK under
  the mnemonic-derived KEK via `wrap_master_key`, splits the AES-GCM
  wire shape into `RecoveryRecord` fields (`wrapped_dek_b64` =
  ciphertext, `tag_b64` = AEAD tag, `nonce_b64` = 12-byte nonce),
  and returns the `MintedRecovery` carrying both the envelope and the
  plaintext mnemonic. The mnemonic is the only in-memory handle on the
  recovery KEK; the caller arranges for the operator to record it
  before this record falls out of scope.
- `unwrap_recovery_envelope(*, envelope, mnemonic)` decodes the
  mnemonic via `decode_mnemonic`, reassembles the AES-GCM wire shape,
  and unwraps the DEK via `unwrap_master_key`. Both decoding failures
  and AEAD tag check failures are surfaced as a single typed
  `RecoveryVerificationError` (P01.S06) so the CLI verb at P05.S04 /
  P05.S05 renders one canonical operator-facing error without leaking
  byte-level detail.
- `verify_recovery_mnemonic(*, envelope, mnemonic)` is the boolean
  variant used by the `aeat config verify-recovery` periodic custody
  test verb (P05.S04).
- `open_session_from_recovery(...)` composes the unwrap with
  `BucketSession.open` so the `aeat config recover` verb (P05.S05)
  yields a live session under the operator's fresh passphrase KEK.

The `_recovery.py` primitives `generate_recovery_key`,
`wrap_master_key`, `unwrap_master_key`, `encode_mnemonic`,
`decode_mnemonic` are untouched — the facade is the only public
surface and the boundary records (`MintedRecovery`, `RecoveryRecord`)
are the canonical I/O shape downstream of P03.

## Tests

`test_recovery_facade.py` (10 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- BIP-39 specification reference vectors: all-zero 256-bit entropy
  encodes to `abandon abandon ... art`; all-ones encodes to
  `zoo zoo ... vote`. Decode-path round-trips the same vectors. These
  are the canonical Trezor `english.json` vectors; the test does NOT
  re-implement the encoder.
- `mint_recovery_envelope` + `unwrap_recovery_envelope` round-trip a
  32-byte DEK.
- The minted envelope is a strict `RecoveryRecord` with the canonical
  `mnemonic_word_count=24` and `hkdf_info` strings.
- A different valid mnemonic raises `RecoveryVerificationError` on
  unwrap (AEAD tag check fails).
- A malformed mnemonic raises `RecoveryVerificationError` (decode
  failure path).
- `verify_recovery_mnemonic` returns True on match, False on mismatch.
- `open_session_from_recovery` yields an unlocked `BucketSession`
  bound to the new bucket id, the new passphrase-derived KEK, and the
  recovered DEK.

`uv run pytest src/aeat/adapters/persistence/storage/master_key/test_recovery_facade.py -x -q` :
10 passed.

`uv run ruff check` clean.
