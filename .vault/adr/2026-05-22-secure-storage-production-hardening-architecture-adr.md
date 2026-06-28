---
tags:
  - '#adr'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
  - '[[2026-05-22-secure-storage-api-review-audit]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
  - '[[2026-05-06-secure-persistence-enforcement-adr]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-state-read-projection-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-06-06-secure-storage-production-hardening-w13-p27-s397-persona-finding-requirements-research]]'
---
# `secure-storage-production-hardening` adr: `canonical SecureStorage architecture for adverse production operation` | (**status:** `accepted`)

## Problem Statement

The secure storage implementation has accumulated strong parts but not a single
enforced production architecture. Existing ADRs mandate secure-object
persistence, profile-bucket identity, explicit custody, profile state
aggregation, and calculation binding vocabulary. The audited codebase still
permits behavior that contradicts those decisions under adverse conditions:
silent key minting, missing custody CLI primitives, provider-level key material
used across buckets, inconsistent idle-lock enforcement, unsafe unsecured
backend selection, sensitive bucket-local JSON stores, explicit database URL
routing, fail-open listing, no storage revision lineage, distributed namespace
constants, eager namespace materialization, and weak passphrase handling.

The result is an unclear SecureStorage API. Application code can treat
`SecureObjectRepository` as a domain repository, bypass active-bucket routing,
or consume partial data without receiving a storage-health contract. That is
not sufficient for production environments where keychain access can fail,
sessions can expire, files can tear, remote sync can be partial, database URLs
can be misconfigured, rows can become unreadable, and calculations can be run
from stale or incomplete evidence.

This ADR defines the architecture the codebase must enroll in before further
SecureStorage expansion is accepted.

## Considerations

The accepted custody and profile-lifecycle ADR chain already requires explicit
operator enrollment through profile creation, passphrase-backed custody,
recovery, profile switch session opening, profile logout teardown, and rotation
semantics. The
accepted secure-persistence enforcement ADR already selects encrypted SQL
secure objects as the governed sensitive persistence boundary. The
profile-bucket lifecycle, profile UUID, profile aggregate, and state projection
ADRs already define operator identity, bucket identity, single write ownership,
and canonical read projection. The repository-binding reconciliation ADR
already separates profile, bucket, bucket session, domain repository,
`SecureObjectRepository`, source observation, and calculation binding.

The missing decision is not vocabulary. It is the mandatory runtime contract
that makes those decisions executable. The storage layer needs a capability
gate that knows whether the active bucket is enrolled, unlocked, fresh,
route-bound, namespace-registered, and integrity-readable. Without that gate,
each caller can accidentally re-derive readiness from incomplete state.

The design must also protect privacy. Profile UUIDs, raw natural object keys,
tax identifiers, wallet balances, filing identifiers, and passphrases must not
escape through diagnostics or repair output. Storage health may use those
values internally, but operator output must stay redacted unless an explicit
profile-management command exists to show a safe label.

The design must support adverse production conditions rather than happy-path
local operation only. Required failure modes include locked or expired sessions,
wrong passphrase, missing recovery wrap, torn manifest, unreadable ciphertext,
explicit database URL attempts, root fallback attempts, partial remote mirror
state, namespace schema mismatch, large namespace scans, and plaintext side
store discovery.

## Constraints

No new root CLI surface is introduced. Custody verbs remain under `aeat config`
as required by the accepted custody ADR and the two-root CLI architecture.

No ordinary production write may route to a database that is not attached to
the active bucket session. Explicit database URLs and root fallback stores are
test or maintenance tools only, and must be blocked from normal operator write
surfaces.

No governed sensitive domain may add new bucket-local plaintext persistence.
Existing plaintext JSON or JSONL stores must either migrate behind secure
objects or receive an explicit accepted exception that names classification,
threat model, retention, export intent, and migration or retirement policy.

Tests for this architecture must use real code paths, real repositories, and
real encrypted stores. They must not use fakes, stubs, mocks, monkeypatches,
skips, xfail shortcuts, or test-local mirrors of production business logic.

The physical encrypted store must remain usable for infrastructure and repair
code, but application code must not treat it as the domain repository API.

## Implementation

Adopt a single SecureStorage hierarchy:

1. Resolve operator input to a profile label or explicit profile target.
2. Resolve the profile target to one private profile UUID.
3. Load and validate the bucket manifest for that profile UUID.
4. Establish or verify one fresh `BucketSession` for that bucket.
5. Build a `StorageRuntime` from the session.
6. Build bucket-attached domain repositories through runtime factories.
7. Resolve registered namespaces and schema policy through the runtime.
8. Load aggregates and projections through owning repositories.
9. Produce source observations and degraded-source diagnostics.
10. Feed calculation bindings from source observations, not from storage.
11. Block filing-grade output when required storage namespaces are degraded.

`StorageRuntime` becomes the mandatory production storage boundary. It owns
the active `BucketSession`, storage readiness, idle-lock freshness, active-route
guard, namespace registry, repository factories, fail-closed listing policy,
object revision policy, and storage-health diagnostics.

`SecureObjectRepository` remains the physical encrypted object store. It stores
encrypted payloads, hashed natural keys, sensitivity classification, schema
version, revision metadata, integrity metadata, and written timestamps. It is
not a domain repository. Domain repositories for profile state, ledgers,
invoices, filings, wallet state, AEAT pulls, auth sessions, calculation
observations, evidence, inventory, and remote sync are built by `StorageRuntime`
and are attached to one bucket session.

Custody is bucket-scoped. Each bucket has a distinct DEK. The DEK is wrapped by
passphrase-derived, recovery-derived, or OS-keystore-cached KEK material. The
unwrapped DEK exists only inside the active `BucketSession`. Provider-level
key material must not be reused as both KEK and DEK across buckets.

Unprovisioned custody fails closed. Key minting is legal only inside explicit
enrollment. Repository construction, reads, writes, listing, raw iteration,
metadata probes, integrity probes, deletes, and save-with-raw-key paths must
fail when the bucket is unenrolled, locked, expired, or route-mismatched.

The namespace registry is mandatory. Every secure-object namespace has one
registry entry with a stable namespace id, owning domain, sensitivity class,
schema version, natural-key grammar, object-key hashing policy, retention
policy, migration policy, repair policy, remote-mirror policy, and partial-read
policy. Domain code imports namespace definitions from the registry instead of
declaring independent string constants.

Default listing fails closed for governed sensitive namespaces. Partial listing
is a separate API that returns typed per-row success and failure diagnostics,
including unreadable counts and reasons. Source resolvers must propagate those
diagnostics to the calculation source mesh.

Secure objects gain revision lineage. Each write records a revision id,
previous revision id or previous payload hash when applicable, payload hash,
ciphertext hash when available, written timestamp, actor or command provenance,
source event id where available, and conflict policy. Upserts that would lose
lineage must either create a new revision or fail through a compare-and-swap
contract.

Storage readiness becomes an API result. A readiness report states whether the
active profile pointer exists, the bucket manifest validates, custody is
enrolled, the bucket session is unlocked and fresh, the database route is
attached to the active bucket, required namespaces are registered, integrity
metadata is readable, and remote mirror state is complete enough for the
requested operation.

Remote storage is a mirror of encrypted objects and integrity metadata. Remote
providers must treat secure-object payloads as opaque ciphertext. Remote sync
must use namespace registry entries, revision metadata, and integrity manifests
to detect partial upload, partial download, conflict, and stale mirror state.

Existing bucket-local JSON and JSONL sensitive stores become backlog items
under this ADR. Each is either migrated to a runtime-created secure-object
domain repository or documented as an accepted exception before further
expansion.

## Rationale

This option is selected because it converts the prior ADR vocabulary into an
enforceable production API. The codebase already has the pieces: profile
identity, bucket directories, secure-object SQL, encrypted payloads, recovery
primitives, source meshes, and projections. The failure is that callers can
still assemble those pieces out of order or bypass them.

Making `StorageRuntime` the production boundary gives every caller the same
answer to the same questions: which bucket is active, whether custody is
usable, whether the session is fresh, whether the route is valid, which
namespace owns this data, what schema and retention apply, whether partial
reads are acceptable, and whether source data is degraded.

Keeping `SecureObjectRepository` as the physical store avoids inventing a new
encryption backend. The refactor is about authority and contract, not replacing
the encrypted SQL substrate.

Fail-closed listing and revision lineage are required because tax calculations
and filing decisions are correctness-sensitive. A readable subset is not a
complete ledger, filing history, wallet state, inventory state, or AEAT pull.
Revision metadata is the only storage-level way to distinguish intended
supersession from conflict, rollback, partial sync, or accidental overwrite.

The namespace registry is required because constants are now architecture, not
convenience values. Namespace id, sensitivity, schema, retention, repair,
remote mirror, and partial-read policy must be centrally auditable.

## Consequences

Direct production construction of physical secure-object repositories becomes
an architectural violation unless it is infrastructure, repair, test isolation,
or explicitly accepted maintenance code. Application code must request typed
domain repositories from `StorageRuntime`.

Several existing flows will fail closed until they are enrolled: wizard and
profile creation paths that rely on silent key minting, config commands missing
custody verbs, list calls that suppress unreadable rows, explicit database URL
write paths, and side stores that persist governed sensitive state outside
secure objects.

The implementation backlog must be ordered by blast radius. Custody and
runtime gates land first. Namespace registry and repository factory migration
land next. Revision metadata and fail-closed listing follow. Side-store
migration, remote mirror hardening, and adverse-condition tests then complete
the production-readiness sweep.

Existing tests that rely on fallback databases, partial lists, or direct
repository construction will need to move to explicit test isolation APIs or
runtime-built repositories. New tests must exercise the real storage stack and
must cover locked sessions, expired sessions, wrong passphrases, route mismatch,
unregistered namespaces, unreadable rows, revision conflicts, partial remote
state, and plaintext side-store policy violations.

This ADR authorizes a multi-wave refactor plan that treats the SecureStorage
API as a production architecture boundary rather than a collection of helper
classes.
