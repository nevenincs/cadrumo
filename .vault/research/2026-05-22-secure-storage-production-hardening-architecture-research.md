---
tags:
  - '#research'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-storage-api-review-audit]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-04-27-secure-persistence-foundation-adr]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-state-read-projection-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---



# `secure-storage-production-hardening` research: `architecture mandate for adverse production operation`

This research consolidates the 2026-05-22 SecureStorage API audit with the
accepted custody, secure-persistence, profile-bucket, profile UUID, aggregate,
projection, and repository-binding ADRs. The purpose is to identify the
architecture that must be mandated before implementation work continues, so
future refactors harden a coherent production storage system instead of
patching individual defects.

## Findings

### 1. The current ADR set defines important parts but not the whole storage contract

The accepted custody and profile-lifecycle ADR chain mandates explicit
enrollment through profile creation, recovery, profile switch session opening,
profile logout teardown, and passphrase-backed key custody. The
secure-persistence enforcement ADR
mandates encrypted SQL secure objects as the governed sensitive persistence
boundary. The profile-bucket lifecycle and profile UUID ADRs define the
operator identity and bucket identity relationship. The profile aggregate and
state projection ADRs define the one-writer and one-read-view pattern. The
profile, bucket, repository, and calculation-binding reconciliation ADR
clarifies vocabulary and execution hierarchy.

Those decisions still leave a gap: there is no single normative architecture
for the SecureStorage API under adverse production conditions. The code can
still silently mint key material, route via explicit database URLs, list
partial encrypted data as if complete, rely on distributed namespace constants,
and persist sensitive bucket-local JSON stores outside the encrypted
secure-object backend.

### 2. Production readiness must be a storage capability, not an incidental side effect

The implementation needs an explicit storage readiness model. A profile label,
active profile pointer, bucket manifest, database path, and repository object
are not proof that storage is usable. Production-ready storage requires a valid
manifest, enrolled custody, unlocked and fresh bucket session, registered
namespace, readable integrity metadata, and a repository path that is attached
to the active bucket.

This is especially important because calculation, filing, remote-pull, and
repair workflows can produce plausible results from incomplete state. If a
namespace has unreadable rows, stale session state, or a fallback database route,
the calculation mesh must receive degraded-source diagnostics rather than
silently consuming the readable subset.

### 3. Key custody must become bucket-scoped and fail closed

The audited key schedule still lets provider-level key resolution behave as
both the key-encryption and data-encryption authority. That conflicts with the
bucket model. A production design needs a distinct per-bucket DEK that is
wrapped by passphrase-derived, recovery-derived, or OS-keystore-cached KEK
material. The unwrapped DEK belongs only to a `BucketSession` for one bucket.

Unprovisioned storage must fail everywhere except the explicit enrollment
flow. Expired, missing, or locked sessions must fail at the storage runtime
boundary before repositories can read, list, decrypt, save, delete, probe
integrity, or iterate raw metadata.

### 4. The repository API needs a runtime boundary above physical secure objects

`SecureObjectRepository` is a physical encrypted object store. It should not be
the application API for profile-bound data. Domain repositories should be built
from a bucket-attached runtime or repository factory that carries the active
bucket session, namespace registry, route guard, and readiness policy.

This changes the architecture from direct construction to a hierarchy:
operator profile resolution, bucket manifest validation, `BucketSession`
activation, repository factory creation, namespace registration, domain
repository access, source observation, calculation binding, and filing/export
decision.

### 5. Namespace constants need a registry with schema, ownership, and retention

The audit found broad secure-object enrollment, but namespace shape is still
distributed across domains and repair logic still uses marker heuristics. That
is not enough for a storage API that must support migration, repair, remote
sync, schema compatibility, and privacy review.

Every secure object namespace needs a registry entry containing at least a
stable namespace identifier, owning domain, sensitivity class, schema version,
natural key grammar, object-key hashing policy, retention policy, migration
policy, repair policy, and whether partial reads are allowed. Domain code
should import namespace definitions from this registry rather than declaring
ad hoc string constants.

### 6. Storage revision lineage is missing from the physical object model

Schema version alone describes payload compatibility. It does not describe
object mutation history, source attribution, compare-and-swap safety, or
conflict resolution. The object model needs storage-level revision metadata:
revision id, previous revision id or previous payload hash, payload hash,
ciphertext hash where available, written time, actor or command provenance,
source event id, and conflict policy.

This is required for remote data pulls, local and remote sync, profile state,
filing records, calculation observations, AEAT wallet snapshots, and recovery
or repair workflows. Without it, upserts can erase prior facts and repair tools
cannot distinguish a legitimate supersession from a conflicting concurrent
mutation.

### 7. Fail-open listing is unsafe for sensitive operational decisions

The current simple list API can suppress unreadable rows and return a readable
subset. That is not a safe default for financial, identity, filing, wallet,
ledger, or calculation namespaces. The production contract should make default
listing fail closed and offer an explicit partial-read API only for callers that
declare and handle incomplete data. Partial reads must carry unreadable counts
and row-level diagnostics into source-mesh degradation.

### 8. Plaintext side stores are architecture exceptions, not implementation details

Bucket-local JSON and JSONL stores currently persist evidence, ledgers,
inventory, live snapshots, and verification data outside the secure-object
backend. The accepted enforcement ADR already makes encrypted SQL secure
objects the normal sensitive persistence boundary. Any retained side store must
therefore be documented as an explicit exception with data classification,
threat model, retention, export intent, and migration plan. Otherwise it should
move behind domain repositories backed by secure objects.

### 9. Explicit database URLs and fallback roots need production route policy

Explicit SQLite URLs and root fallback databases are useful for tests and
maintenance, but they are dangerous in normal CLI write flows. The storage
runtime should reject production writes unless the repository route is attached
to the active bucket session. Test or maintenance exceptions must be explicit,
audited, and unavailable to ordinary operator commands.

### 10. Remote storage must be a mirror, not a second trusted plaintext store

Drive or local filesystem provider surfaces should treat secure-object payloads
as opaque ciphertext plus integrity metadata. Remote sync must not create a
parallel plaintext persistence model. Remote providers need namespace
registration, revision metadata, integrity manifests, and conflict policy so
eventual consistency or partial upload cannot be mistaken for complete local
state.

## Architecture Direction

The corrective architecture should mandate a `StorageRuntime` or strengthened
`BucketSession` as the only way to create profile-bound repositories. That
runtime owns custody readiness, idle-lock freshness, active-bucket route
binding, namespace registry access, repository factories, object revision
policy, integrity diagnostics, and explicit partial-read behavior.

The physical `SecureObjectRepository` remains the encrypted storage primitive.
It is not the application API. Application code should consume typed domain
repositories created by the runtime. Calculation code consumes source
observations and degraded-source diagnostics, not raw storage repositories.

## Required Refactor Themes

The hardening work should proceed in waves: custody fail-closed gates, storage
runtime and repository factory, namespace registry, revision and integrity
lineage, plaintext side-store migration or exception recording, remote mirror
policy, and adverse-condition tests.
