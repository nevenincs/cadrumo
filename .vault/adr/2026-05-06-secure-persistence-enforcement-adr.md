---
tags:
  - '#adr'
  - '#secure-persistence-enforcement'
date: '2026-05-06'
modified: '2026-07-17'
related:
  - '[[2026-05-06-secure-persistence-enforcement-research]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-06-04-secure-object-backlog-drain-adr]]'
  - '[[2026-06-04-secure-object-integrity-adr]]'
---

# Secure persistence enforcement | (**status:** `accepted`)

## Decision

Governed application records persist through the canonical encrypted storage
substrate under `cadrumo.adapters.persistence.storage`. SQL
`SecureObjectRepository` is the normal repository boundary for encrypted
records. Profile buckets provide the custody, key, lifecycle, and sealed
archive boundary; they do not create a second plaintext repository path.

The deleted foundation-wave ADRs are not compatibility contracts. Their live
security properties are consolidated here and in the focused bucket, passkey,
hardening, and integrity ADRs linked above.

## Mandatory invariants

- Every persisted record declares a `SensitivityClass`. Governed secret,
  session, identity, financial, audit, cache, corpus, and diagnostic material
  follows the policy for that class.
- `SecureObjectRepository` stores encrypted bytes in SQL and binds natural
  lookup identity through the canonical hashed-lookup mechanism. Loads and
  scans validate the expected sensitivity class and supported schema version.
- Encryption uses authenticated encryption. Bucket passphrases derive key
  encryption keys with the canonical Argon2id parameters; custody and recovery
  remain governed by the focused passkey and bucket decisions.
- Repository identifiers pass through the shared path-safety boundary. Local
  copies of the same validation logic are prohibited.
- Public corpus material may remain plaintext only under the corpus policy; its
  integrity is verified through the canonical manifest mechanism.
- Ordinary persistence must not materialise governed plaintext through direct
  file writes, ad hoc temporary files, or an alternate envelope repository.
  Explicit operator exports are boundary crossings and must be identifiable as
  exports, not repository writes.
- Read and write failures are typed and fail closed. Classification, integrity,
  key-custody, and schema-version mismatches are never silently accepted.

## Compatibility boundary

The repository is pre-release and follows delete-not-migrate hard cutover for
obsolete persistence designs. There is no obligation to retain legacy
read-through, deprecated path fallbacks, deprecation logging, dual-write code,
or one-shot migration helpers described by the deleted wave ADRs. Deprecated
file and envelope shapes are not alternative authorities.

Secure objects accept the current schema version exactly. Pre-current and
future versions are refused; no dormant upgrader or revision registry is kept.
Any future format change requires a new approved current-format decision and a
hard cutover, not a legacy storage path or retained helper API.

## Architecture boundaries

- Domain and application repositories depend on their declared ports; concrete
  SQL, bucket, key, and archive implementations live under adapters.
- The secure-object namespace registry is the authority for persisted object
  families. A new family must declare its classification and schema contract
  before it writes.
- Bucket custody and SQL secure objects form one storage architecture. A feature
  must not introduce a parallel durable writer for the same governed record.
- Operational configuration and deliberate exports require explicit policy;
  neither is a precedent for plaintext application-state persistence.

## Consequences

Security review has one current persistence decision instead of a sequence of
wave diaries. New writers are assessed against the encrypted SQL/bucket
substrate, classification policy, integrity checks, and real-behaviour tests.
An older record that requires a retired read path is rejected rather than
reviving compatibility code.
