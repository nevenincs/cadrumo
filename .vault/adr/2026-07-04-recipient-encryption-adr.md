---
tags:
  - '#adr'
  - '#recipient-encryption'
date: '2026-07-04'
modified: '2026-07-17'
related:
  - "[[2026-07-04-recipient-encryption-research]]"
---

# `recipient-encryption` adr: `Recipient-fingerprint registry and encrypt-for-recipient transport` | (**status:** `accepted`)

## Problem Statement

Issue #421 landed four slices (checksum-integrity build/verify, ed25519
signing, counter-sign receipt, CLI wiring) and its own closing-candidate
comment named the remaining, genuinely-unbuilt scope. Two of those items are
targeted here: a **recipient fingerprint registry** (a taxpayer records who
their accountant/gestor is, by a public-key fingerprint they can verify
out-of-band) and **encrypt-for-recipient** (a review package encrypted so
*only* the named recipient's private key can open it, as opposed to the
existing sign/counter-sign flow, which proves authorship and integrity but
leaves the package itself in plaintext ZIP form). Review-only workspace mode,
package expiry/replay defence, and audit-tag enrolment remain out of scope for
this slice and stay open on #421.

## Considerations

- `sensitive-financial-data-secure-storage-only`: any private key material
  must persist only as ciphertext through `SecureObjectRepository`; decrypted
  bytes exist only transiently in process memory; nothing is staged to a temp
  file.
- `aeat-safety-legal-gates`: this feature performs no AEAT submission of any
  kind; it only prepares a bundle for a human accountant to receive and act on
  outside the application.
- `composition-service-no-parallel-write-path`: the AEAD primitive
  (`encrypt_record`/`decrypt_record`, `derive_key`) and the review-package
  integrity primitive (`verify_corpus_bundle`/`assert_review_package_verifies`)
  already exist and must be reused, not re-implemented.
- `aeat-schema-central-config` / no-invented-crypto: the asymmetric primitive
  must come from an already-vetted, already-depended-upon library.
  `cryptography>=47.0.0,<48` (installed: 48.0.0) ships `X25519PrivateKey`/
  `X25519PublicKey` and `HKDF` — no new dependency is required.
- `aeat-architecture-boundaries`: the CLI root is `config`/`app` only; the
  original issue's `aeat configure collab ...` verb family predates the CLI
  redesign and cannot be used verbatim.
- `no-legacy-compatibility`: this is a from-birth feature; no migration
  surface, no back-compat shape.
- `aeat-roundtrip-discipline`: the fingerprint registry is a persistence
  boundary and needs a strict save/load/equality roundtrip plus an
  anti-tautology proof, mirroring `BienesInversionIvaRegisterRepository`'s
  established pattern.

## Considered options

- **Option A — X25519 ECDH + HKDF-SHA256 + existing AES-256-GCM AEAD
  (ECIES-style), composed entirely from primitives already in
  `cryptography`.** Ephemeral sender X25519 keypair per encryption, ECDH
  against the recipient's long-term public key, HKDF derives the AEAD key
  bound to both public keys as context, `encrypt_record` performs the AEAD.
  Zero new dependencies; every sub-primitive (`X25519`, `HKDF`,
  `AESGCM`-via-`encrypt_record`) is already used elsewhere in the codebase.
  **Chosen.**
- **Option B — age (rage/pyrage) or PGP (python-gnupg) as an external
  encrypt-for-recipient tool.** Both are mature, purpose-built recipient-
  encryption formats. Rejected for this slice: neither `age`/`rage` nor a PGP
  binding is a current project dependency; adding one is a new supply-chain
  surface for a single verb, when the same guarantee is achievable by
  composing primitives already vetted and already shipped. Revisit only if a
  future requirement (multi-recipient fan-out, existing PGP keyring
  interoperability with the accountant's own tooling) makes a standard
  container format worth the new dependency.
  age's actual design (X25519 + HKDF + ChaCha20-Poly1305, wrapped per
  recipient) is structurally the same construction as Option A; Option A gets
  the same cryptographic shape without the new dependency.
- **Option C — reuse the existing Ed25519 signing keypair for encryption.**
  Rejected outright: Ed25519 is a signature-only curve (EdDSA), not designed
  for Diffie-Hellman key agreement; mixing signing and encryption keys is a
  well-known cryptographic anti-pattern (key-reuse across purposes weakens
  both). A distinct X25519 keypair, in its own namespace, is required.

## Constraints

- This ADR governs a NEW keypair type (`X25519`) and a NEW registry entity
  (recipient fingerprints); it does not touch the ed25519 signing/counter-sign
  primitives, which remain independent and unchanged.
- No CLI verb wiring is decided as in-scope for the first landed slice; the
  registry and the encrypt-for-recipient function are built as directly
  importable, fully tested application-layer primitives. CLI wiring
  (`aeat config collab recipient add/list/remove` and
  `aeat app modelo review-package encrypt-for-recipient`) is named here as the
  intended future placement so a follow-up slice does not have to re-litigate
  it, but is not built in this pass.
- The registry stores each recipient's **public** key plus a display
  fingerprint (SHA-256 of the raw public key bytes, hex-encoded, the
  conventional "fingerprint" a human can read aloud/compare out-of-band). It
  never stores a recipient's private key — the recipient generates and keeps
  their own keypair; the taxpayer only records the recipient's public half.
- Every recipient's own encryption keypair (the key material the taxpayer
  mints for THEMSELVES to receive encrypted feedback, symmetric to the
  signing-keypair pattern) is out of scope for this ADR's first slice; the
  registry here is taxpayer-side storage of OTHER PEOPLE's public keys.
  Minting the taxpayer's own X25519 keypair (so an accountant could encrypt
  something back to Kent) is deferred to whenever the reverse flow is needed;
  the immediate ask (`--encrypt-for-recipient`) only requires the recipient's
  public key, never a keypair of the sender's own for this direction (ECIES
  uses an ephemeral sender keypair generated fresh per message, not a
  persisted one).

## Implementation

**Recipient fingerprint registry** (`cadrumo.application.modelo._recipient_registry`
or a comparably-scoped new module): a typed, frozen `RecipientFingerprintRegister`
(tuple of `RecipientFingerprintRecord`) persisted as one `FINANCIAL`-sensitivity
secure object per bucket, following the exact shape of
`BienesInversionIvaRegisterRepository`: `load()` returns an empty register when
absent, `add(record)` re-loads current state and refuses a duplicate
`recipient_id`, `remove(recipient_id)` refuses a missing id, `list()` returns
the tuple. Each `RecipientFingerprintRecord` carries: `recipient_id` (operator
label, e.g. `"kents-accountant"`), `public_key_hex` (raw 32-byte X25519 public
key, hex), `fingerprint_sha256` (computed field: SHA-256 of the raw public key
bytes, hex, for out-of-band verification display), `label` (free-text
display name), `added_at` (timezone-aware datetime). A new
`SecureObjectNamespaceDefinition` (`RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE`)
is registered in `_namespace_registry.py` next to the review-package signing
namespace, at `sensitivity=SensitivityClass.FINANCIAL` (the registry is
sensitive collaborator metadata, one tier below the taxpayer's own SECRET
private key).

**Encrypt-for-recipient primitive** (a new module, e.g.
`cadrumo.application.modelo._review_package_recipient_encryption`): a function
`encrypt_review_package_for_recipient(package_path, *, recipient_public_key_hex)
-> bytes` that (1) reads the package bytes into memory, (2) generates a fresh
ephemeral X25519 keypair, (3) performs ECDH against the recipient's public key,
(4) derives a 32-byte AES key via `derive_key` with a fixed HKDF `context`
binding "aeat.review_package.recipient_encryption.v1" plus both public keys as
salt/context material so a key can never be reused across a different
recipient or a different ephemeral sender key, (5) calls `encrypt_record` to
AEAD-encrypt the package bytes, associated data binding the recipient's public
key (so a ciphertext cannot be silently re-targeted at a different recipient
without detection), and (6) returns a small typed wire envelope (ephemeral
sender public key + `EncryptedBlob` wire bytes + recipient public key hex,
enough for the recipient to reverse the ECDH and derive the same key). A
paired `decrypt_review_package_for_recipient(envelope_bytes, *,
recipient_private_key) -> bytes` performs the mirror operation. Both functions
operate entirely on in-memory bytes; the caller writes the returned ciphertext
to the operator-specified output path, and the plaintext package bytes are
never written to disk by this module.

Neither function opens a `SecureObjectRepository` write path itself for the
review package (the review-package build/sign modules already own that); this
module's only persistence touchpoint is reading the recipient's public key
back out of the fingerprint registry, which the CLI wiring slice will compose.

## Rationale

Option A was chosen because every sub-primitive (X25519 key agreement, HKDF
key derivation, AES-256-GCM AEAD via `encrypt_record`) is already a dependency
of `cryptography` 48.0.0 and already exercised elsewhere in this codebase (HKDF
in the master-key wrap path, AES-256-GCM in every secure-object row). This
directly satisfies the operator mandate to never invent crypto: composing
already-vetted primitives in a textbook ECIES shape carries far less risk than
either hand-rolling a novel scheme or adding a new external dependency (age/PGP)
whose supply-chain and API surface would need its own vetting pass for a single
verb. The recipient registry mirrors `BienesInversionIvaRegisterRepository`
exactly (per `aeat-roundtrip-discipline` and existing project convention for
small typed catalogues), so its persistence boundary, duplicate-id refusal, and
test shape are drop-in familiar rather than novel.

## Consequences

- Gains: the taxpayer can now record a trusted recipient's public-key
  fingerprint once, verify it out-of-band (read-aloud/compare), and use it
  repeatedly to seal a review package so only that recipient can open it —
  closing the last piece of #421's "Kent success moment" that is a pure
  cryptographic primitive rather than a workflow-state feature (review-only
  mode, expiry, audit tags).
- Difficulty: because ECIES uses a fresh ephemeral sender keypair per message,
  there is no sender-side "my encryption identity" to publish — only the
  recipient's public key matters for this direction. A future reverse flow
  (accountant encrypts feedback back to Kent) will need the taxpayer to mint
  their own long-term X25519 keypair, symmetric to the signing keypair; that
  is out of scope here and tracked as a natural follow-up.
- Pitfall avoided: reusing the Ed25519 signing keypair for encryption was
  explicitly rejected (Option C) to avoid the well-known cross-purpose
  key-reuse hazard.
- Opens: CLI verb wiring (`aeat config collab recipient add/list/remove`,
  `aeat app modelo review-package encrypt-for-recipient`), locale key
  authoring via the locale CLI, and eventually a decrypt-side verb for the
  recipient (out of this taxpayer-side ADR's scope, since the recipient is
  presumed to run their own tooling or a future symmetric CLI surface).
