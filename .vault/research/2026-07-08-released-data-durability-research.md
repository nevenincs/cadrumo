---
tags:
  - '#research'
  - '#released-data-durability'
date: '2026-07-08'
modified: '2026-07-09'
related: []
---

# `released-data-durability` research: `long-term readability of persisted taxpayer data`

Operator-raised durability concern, verified 2026-07-08 by a read-only audit of the
persistence, key-management, and export surfaces. A Spanish tax filing must remain
retrievable and provable for years (LGT art. 66 prescription is four years as the
routine horizon, longer for some obligations), so the encrypted on-disk store —
taxpayer profiles, filed-return records and evidence, the ledger, calculation
revisions, justificantes, attachments — must stay readable across application
upgrades. The audit asked whether a persisted-format change can strand years-old
records, given the standing no-legacy posture ("old is deleted, not maintained",
premised on the project being unreleased pre-beta with no released data).

## Findings

### Cryptographic durability is sound

- Passphrase → Argon2id KEK (`master_key/_kdf.py`), parameters persisted per bucket
  in the manifest with a version field (`bucket/_manifest.py`), so a future KDF
  cost-bump is non-breaking by construction.
- The KEK wraps a per-bucket AES-256-GCM data-encryption key bound to the bucket id
  via AEAD AAD (`master_key/_dek_wrap.py`); a passphrase change rewraps the DEK
  without touching ciphertext; master-key rotation re-encrypts per-file atomically
  (`storage/_rotation.py`).
- Recovery is a 24-word BIP-39 mnemonic wrapping the master key
  (`master_key/_recovery.py`, `_recovery_facade.py`), surfaced as
  `aeat config recover / rekey / show-recovery / verify-recovery`.

### Format durability is absent: every version gate is strict equality

- Secure-object rows: `sql/_secure_object_row_codec.py` raises
  `EnvelopeVersionError` whenever `row.schema_version != max_supported_version` —
  an older row fails identically to a futuristic one. The registered-namespace
  check in `sql/secure_objects.py` (`_enforce_registered_row_schema`) repeats the
  same strict equality. There is no per-version decode dispatch, no
  migrate-on-read, no upgrade path anywhere.
- Profile bundle: `application/user_profile/_bundle.py` declares
  `SUPPORTED_BUNDLE_SCHEMA_VERSIONS = frozenset({3})` — the schema went v1→v2→v3
  and each prior version was dropped rather than kept readable.
- Sealed bucket archive: `application/bucket_maintenance/_service.py` refuses any
  header whose `archive_schema_version` differs from the current constant (2);
  the import/export test suite asserts a v1 archive is refused. The escrow
  artefact a taxpayer would keep as a long-term backup churns with the app.
- All secure-object namespaces are currently at schema version 1
  (`storage/_namespace_registry.py`), so nothing is stranded today; the first
  version bump under the current gates would make every previously written row
  in that namespace unreadable, and the no-legacy rule forbids writing a bridge.

### Serialization posture

Persisted payloads ride strict frozen pydantic models
(`STRICT_FROZEN_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")`,
`core/_models.py`). The roundtrip discipline proves save→load within one code
version only; with `extra="forbid"` plus required fields, model evolution makes
previously persisted bytes fail loudly on load even without a version bump.
Nothing loads "yesterday's bytes under today's model".

### Governance gap

The no-legacy rule blesses "a `max_supported_version` ceiling that refuses a
FUTURE shape" as forward-compatibility to keep — but the implementation is exact
match, not a ceiling, and no accepted ADR governs retention, forward-migration,
or durability for released data. The rule's own premise ("no released data")
expires at first release with no flip condition recorded anywhere.

### Verdict

PARTIAL. Keys and ciphertext are durable; formats are not. The gap is structural
and cheap to close now while every format sits at its current single version: no
migration code is needed, only ceiling semantics, an explicit (empty) upgrade
dispatch, and a gate that makes a future version bump without a registered
upgrade path a loud CI failure instead of silent data stranding.
