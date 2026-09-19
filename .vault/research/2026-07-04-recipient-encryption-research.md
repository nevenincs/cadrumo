---
tags:
  - '#research'
  - '#recipient-encryption'
date: '2026-07-04'
modified: '2026-07-04'
body_hash: 'sha256:cc9c397e0a099f85d66f7a9d9a5fdaab7615298c143d11b8cd693f4b57ee9b95'
related: []
---

# `recipient-encryption` research: `Recipient-fingerprint registry and encrypt-for-recipient transport`

Grounding pass for the remaining scope of issue #421 ("Kent can share a signed
review package with his accountant and receive countersigned feedback").

## Issue #421 exact remaining ask

Four slices of #421 already shipped (build/verify integrity, ed25519 sign,
counter-sign receipt, CLI wiring). The issue's own closing-candidate comment
(2026-07-01) named five genuinely-unbuilt items and recommended splitting them
into a successor issue if wanted:

- Recipient fingerprint registry (`aeat configure collab recipient add/list/remove`
  in the original issue text).
- Review-only workspace mode.
- Package expiry / replay defence.
- `collab_event` / `privacy_event` audit-tag enrolment.
- **Encryption-for-recipient** (`--encrypt-for-recipient` in the issue's success
  moment) — the delivered flow is sign/verify only, not encrypt-for-recipient
  transport.

No successor issue exists yet (`gh issue list` search for
"recipient encryption fingerprint registry" returns only #421 itself). #421
remains OPEN and still carries this scope in its own issue body. This dispatch
targets exactly the two items named in the operator brief: the recipient
fingerprint registry and the encrypt-for-recipient primitive.

## Existing crypto/storage substrate (do not re-invent)

- `cryptography>=47.0.0,<48` is already a hard project dependency (confirmed
  version 48.0.0 installed). It ships `X25519PrivateKey`/`X25519PublicKey`
  (`cryptography.hazmat.primitives.asymmetric.x25519`) and `HKDF`
  (`cryptography.hazmat.primitives.kdf.hkdf`) — both importable in the current
  environment. No new dependency is needed for asymmetric (public-key)
  encryption; X25519 ECDH + HKDF + the project's existing AES-256-GCM AEAD
  primitive composes to a standard ECIES-style construction.

- `src/aeat/adapters/persistence/storage/crypto/_crypto.py` (re-exported via
  `crypto/__init__.py`) is the at-rest AEAD substrate: `encrypt_record` /
  `decrypt_record` (AES-256-GCM, 12-byte random nonce, `EncryptedBlob` wire
  shape `nonce || ciphertext_with_tag`) and `derive_key` (HKDF-SHA256, takes
  `key_material`, `salt`, `context` info-binding, `length`). This is the
  correct primitive to derive the per-message symmetric key from the X25519
  shared secret and to perform the actual AEAD encryption — no new AEAD
  logic should be written.

- `src/aeat/application/modelo/_review_package_signing.py` is the closest
  structural analogue for a per-profile keypair: `ReviewPackageSigningKeypair`
  (private+public hex, `bucket_id`, `created_at`), minted once per bucket via
  `ensure_review_package_signing_keypair` (idempotent: loads existing via
  `SecureObjectRepository.load(...)`, else `Ed25519PrivateKey.generate()` then
  persists via `.save(..., classification=SensitivityClass.SECRET, ...)`), and
  a `ReviewPackageSigningPublicKey` projection that is safe to export/print.
  The recipient-encryption keypair (for accepting encrypted bundles) should
  follow the identical shape but with `X25519PrivateKey`/`X25519PublicKey` in
  place of Ed25519, and a distinct `SecureObjectNamespaceDefinition` (own
  `namespace=` string, own `key=`) registered in
  `src/aeat/adapters/persistence/storage/_namespace_registry.py` next to
  `MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE` (same `sensitivity=SECRET`
  pattern).

- `src/aeat/adapters/persistence/profile/bienes_inversion.py`
  (`BienesInversionIvaRegisterRepository`) is the closest structural analogue
  for a small typed catalogue/registry with `.add()` duplicate-id refusal:
  loads a `FINANCIAL`-sensitivity singleton secure object (empty register when
  absent), `.add(record)` re-loads, checks `any(existing.identifier ==
  record.identifier ...)`, raises a typed domain error on collision, else
  appends and re-saves. The recipient fingerprint registry should mirror this
  exact shape: a `RecipientFingerprintRegister` singleton (frozen pydantic
  list of `RecipientFingerprintRecord`), one repository with `add`/`remove`/
  `list`, keyed by a stable `recipient_id` (operator-chosen label, e.g. "kent's
  accountant") with the fingerprint's public key hex + a SHA-256 fingerprint
  string for display/verification, stored at `SensitivityClass.FINANCIAL` (a
  registry of a taxpayer's collaborators is sensitive metadata, though not as
  secret as the taxpayer's own private key).

- Review-package build/sign/counter-sign already established the sensitive-data
  posture this feature must inherit: private keys are minted once, persisted
  ONLY as ciphertext through `SecureObjectRepository`, never logged, never
  written to a plaintext file, and exist as raw bytes only transiently in
  process memory. `sensitive-financial-data-secure-storage-only` governs the
  bundle bytes; encrypt-for-recipient must decrypt source review-package bytes
  into memory only and never stage a decrypted intermediate on disk — the
  ciphertext output (the ECIES-wrapped bundle) is the only artefact written to
  the operator's requested output path, matching the existing sealed-archive
  writer's "no tmp+rename staging, direct write to caller path" contract.

## CLI surface placement

The CLI root is `config` and `app` only (`aeat-architecture-boundaries`); the
original issue's `aeat configure collab ...` vocabulary predates the CLI
redesign and is not a valid target. Confirmed via `aeat config --help`: no
`configure` root exists. The `review-package` verb group already lives under
`aeat app modelo review-package {build,verify,sign,verify-signature,
counter-sign,verify-receipt}`. Two placement decisions follow:

- The recipient fingerprint registry (persistent trust configuration, not a
  filing action) fits the `config` root's shape best, mirroring
  `aeat config auth providers/configure/status/test/clear`  — a plausible new
  group is `aeat config collab recipient add/list/remove` (naming avoided:
  "collab" is retained from the issue vocabulary only as a grouping noun, not
  a reused module name — see `aeat-spanish-stem-naming`'s English-noun
  carve-out for cross-cutting framework concepts).

- The encrypt-for-recipient action operates on a built review package (same
  subject as `sign`/`counter-sign`), so it fits as a new
  `aeat app modelo review-package encrypt-for-recipient` verb alongside the
  existing four.

This research intentionally scopes the CLI verb wiring as a candidate for a
follow-up slice; the first landed slice (per the operator brief) is the typed
recipient-fingerprint registry with its encrypted persistence, plus the
encrypt-for-recipient primitive module (both consumable from Python and ready
for CLI wiring), decided in `[[2026-07-04-recipient-encryption-adr]]`.
