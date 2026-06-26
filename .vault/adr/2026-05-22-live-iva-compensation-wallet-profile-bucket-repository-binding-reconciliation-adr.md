---
tags:
  - '#adr'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-04-17-aeat-access-gate-adr]]'
  - '[[2026-04-17-session-persistence-adr]]'
  - '[[2026-04-16-live-cert-auth-adr]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
  - '[[2026-05-26-modelo-130-relation-regression-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-state-read-projection-adr]]'
---

# `live-iva-compensation-wallet` adr: `profile, bucket, repository, and calculation-binding hierarchy` | (**status:** `accepted`)

## Problem Statement

The wallet hardening and secure-object repair wave now depends on several
accepted ADRs that use overlapping words for different layers. Profile, bucket,
active profile, repository, binding, authority, and reconciliation are all
valid terms, but they are currently overloaded across storage, CLI, auth,
repair, and calculation surfaces.

That overload is no longer a documentation problem only. It affects privacy,
storage routing, calculation confidence, and live AEAT safety. A repair command
that prints an active bucket UUID as a profile leaks an operational identifier.
A calculation path that opens a repository without the intended bucket session
can read or write the wrong database. A binding resolver that bypasses storage
health can produce a plausible all-zero or stale Modelo 303/390 result while
critical evidence rows are unreadable.

The project needs one binding vocabulary and one hierarchy that reconciles the
secure-storage ADRs, profile lifecycle ADRs, UUID identity ADR, aggregate ADR,
state projection ADR, calculation source mesh ADR, and live IVA wallet ADR.

## Considerations

The May 14 profile-bucket lifecycle ADR establishes the storage architecture:
profile is the user-facing identity, bucket is the encrypted storage slice, and
the cardinality is 1:1. The May 16 lifecycle CLI ADR keeps that storage
architecture but requires the operator CLI to speak in profile terms. The May
21 UUID identity ADR decouples mutable labels from immutable storage identity:
operators type labels, but paths, pointers, keys, token filenames, and bucket
directories use UUIDs.

The profile aggregate ADR establishes that profile state is not a loose set of
files and secure-object rows. One aggregate and one repository own writes
across manifest, pointer, encrypted record, token/lock files, lifecycle state,
and storage directories. The state projection ADR establishes the read-side
companion: operator surfaces consume one canonical projection instead of
re-deriving readiness from partial store subsets.

The secure-object drift research shows the failure mode when this hierarchy is
not enforced. Default SQL repository construction can route through settings to
the active bucket, an explicit database URL, or a fallback root database.
Ephemeral-key tests that missed database isolation produced unreadable rows in
profile-local storage. Repair and calculation confidence must therefore treat
repository routing and bucket session as correctness inputs.

The calculation source mesh ADR uses binding for modelo source inputs and
resolver-owned values. This is not the same as storage binding. Registry
bindings describe calculation inputs. Application source resolvers read
bucket-attached repositories and produce typed source observations. The
calculation engine consumes the source resolution envelope; it does not open
repositories itself.

The live IVA wallet ADR adds an external authority source. Wallet evidence is
read-only AEAT state. Local recurrence is comparison and fallback evidence.
Taxpayer override is explicit. A persisted non-blocking reconciliation decision
is the only value that may affect Modelo 303 compensation.

## Constraints

No live AEAT filing, payment, representation choice, confirmation, or
submission action is authorized by this ADR. Wallet acquisition remains
read-only and guarded by the existing live-read safety policy.

Repair and attribution surfaces must remain non-destructive unless a later step
records an explicit preserve-first decision and replacement evidence. This ADR
does not authorize quarantine or deletion.

Operator inventory and repair output must not print taxpayer identifiers,
expediente identifiers, wallet amounts, filing identifiers, natural secure
object keys, or profile UUIDs. Explicit profile management commands may show
operator labels because their job is profile inventory; repair and diagnostic
inventory commands must use redacted context.

Tests for this hierarchy must use real code paths and real repositories. They
must not use fakes, mocks, monkeypatches, skipped tests, xfail shortcuts, or
test-local business logic mirroring calculation rules.

## Implementation

Adopt the following canonical terminology.

`profile` is the operator-facing tax identity or account. It is what a user
creates, switches, shows, edits, exports, imports, or deletes.

`profile_label` or display name is the mutable, human-readable name. It may be
used for command entry and explicit profile inventory. It is not an identity and
must not be used in keys, paths, pointer values, token filenames, or secure
object natural keys.

`profile_uuid` is the immutable generated storage identity. It is opaque and
private. It is the value used for the bucket directory, bucket manifest
identifier, active pointer, token and lock filenames, and secure-object keys.
It must not be printed on repair, attribution, or diagnostic inventory
surfaces.

`bucket` is the encrypted storage slice attached 1:1 to one profile UUID. It
owns the secure-object database, blob store, audit store, manifest, lockfile,
and key material for that profile.

`bucket_manifest` is plaintext routing and lifecycle metadata. It may carry
UUID, label, schema, KDF, recovery and status metadata. It must not carry tax
facts, taxpayer identifiers, wallet balances, passphrases, derived keys, or
wrapped payloads.

`active_profile_pointer` is the plaintext selector that stores the active
profile UUID. It is routing state, not proof that the profile record, manifest,
or secure-object rows are readable.

`BucketSession` is the unlocked cryptographic and database context for one
bucket. It owns active key material, engine handles, repository factories, and
bucket-scoped memoization. Repository access for profile-bound state must flow
through this session or an explicit test/diagnostic database isolation path.

`domain repository` is a typed application or domain persistence boundary such
as profile, ledger, invoice, filing, wallet, calculation observation, or auth
session storage. A domain repository must be bucket/session-attached when it
handles profile-bound data.

`SecureObjectRepository` is the physical encrypted store. It is not by itself a
domain repository and it must not be treated as a calculation source. Its raw
object keys are HMAC digests and raw rows are ciphertext.

`calculation binding` is a registry/modelo input requirement or resolved value.
It is separate from profile/bucket attachment. The calculation source mesh owns
the transition from bucket-attached domain evidence to calculation bindings.

`source observation` is typed evidence produced by an application resolver from
ledger, invoices, profile facts, filed history, wallet evidence, censo, or other
source domains.

`reconciliation decision` is an immutable authority selection among AEAT wallet
evidence, filed-history evidence, local recurrence, and explicit taxpayer
override. Calculation consumes decisions, not live adapters.

Adopt this hierarchy for command and calculation execution:

1. Resolve operator input from profile label to profile UUID.
2. Resolve the active pointer or explicit command target to one profile UUID.
3. Load and validate the bucket manifest for that UUID.
4. Establish or verify the `BucketSession` for that bucket.
5. Build bucket-attached repository factories from the session.
6. Load profile/workspace aggregates through their owning repositories.
7. Build the canonical operator state projection for read surfaces.
8. Run application source resolvers against bucket-attached domain repositories.
9. Feed typed source observations into the calculation source mesh.
10. Produce registry calculation bindings and diagnostics.
11. Consume only persisted, non-blocking reconciliation decisions for AEAT
    remote-state values.
12. Block calculation/export when required source namespaces are degraded and no
    verified replacement evidence or preserve-first decision exists.

Repair and diagnostics adopt the same hierarchy but use redacted output. The
system may use the profile UUID internally for matching, digest correlation,
repository routing, and confidence classification. Public repair output names
that context as active profile, selected profile, other profile, or unknown
profile without printing the UUID.

Calculation confidence is now part of storage health. A source resolver must
report the evidence namespaces it depends on. If those namespaces contain
unreadable or integrity-failed rows, the resolver must produce degraded-source
diagnostics. The mesh must prevent automatic filing-grade output when a
degraded source can affect ledger IVA, periodic Modelo 303, annual Modelo 390,
multiyear compensation carry-forward, wallet reconciliation, or filed-history
reconciliation.

## Rationale

This decision reconciles the existing ADRs instead of replacing them. The
storage layer keeps bucket and `BucketSession` because those are precise
engineering concepts. The operator layer keeps profile because users manage tax
identities, not storage buckets. The UUID identity ADR resolves rename and path
corruption by making the UUID the only stable identity. The aggregate and
projection ADRs ensure one writer and one read view. The source mesh and wallet
ADRs keep calculation and live AEAT evidence separate from storage mechanics.

The most important practical outcome is that "active profile" stops being a
catch-all. It is either a label, a UUID pointer, an unlocked session, a loaded
aggregate, or a projection field. Each layer has different privacy and
correctness rules. Naming them explicitly prevents repair output from leaking
UUIDs, prevents repositories from silently routing to the wrong database, and
prevents calculations from hiding degraded evidence behind plausible results.

## Consequences

W05 repair work must classify unreadable rows with internal UUID-aware context
while keeping public output redacted.

W05 remediation planning must be profile-local and non-destructive by default.
Quarantine or rebuild decisions require verified replacement evidence and must
not be inferred from namespace names alone.

Calculation confidence work must join secure-object integrity to source mesh
coverage. Ledger, invoice, filing, wallet, filed-history, and calculation
observation degradation must become visible to Modelo 303, Modelo 390,
multiyear carry-forward, and AEAT remote-state reconciliation.

Tests must include public CLI privacy contracts, repository-routing contracts,
source-mesh degraded-evidence contracts, and persona-driven CLI testimonials.
They must assert behavior through real code paths and real encrypted stores.

Future ADRs that use the word binding must state whether they mean calculation
binding or storage attachment. Future ADRs that use active profile must state
which layer is meant: label, UUID pointer, session, aggregate, or projection.

## 2026-05-26 Execution-Control Amendment

This amendment binds the current live IVA execution plan to this ADR and its
related ADR chain. The amendment does not authorize live filing, payment,
represented-taxpayer submission, form confirmation, or synthetic input to AEAT.
It only authorizes read-only acquisition, storage, diagnostics, reconciliation,
and calculation gating work when the corresponding plan rows remain inside the
constraints below.

Live authentication diagnostics are in scope because the profile/bucket/session
hierarchy is meaningless if the system cannot prove which configured profile is
being authenticated. Diagnostics may report redacted identity-shape facts such
as whether DNI/NIE, support-number, certificate, Cl@ve preference, timeout, and
active profile are configured. Diagnostics must not print taxpayer identifiers,
support-number values, wallet amounts, filing identifiers, expediente ids,
profile UUIDs, passphrases, or token material.

Read-only Sede acquisition is in scope as an application/backend capability,
not as a CLI-only behavior. A CLI may invoke acquisition, but the architecture
boundary is the backend service that authenticates, reads filed-history and
wallet/cartera evidence where available, returns typed evidence, and returns
typed failures. Wallet failure must not discard filed-history success. Filed
history and wallet state remain separate source observations.

Representation-gate handling is in scope only for own-profile read navigation
where AEAT requires identity confirmation to reach a read surface. This ADR
does not authorize representative filing, represented-taxpayer selection,
payment, filing, or confirmation submission. The no-synthetic-Sede ADR remains
binding: live tests and drivers must not send synthetic data to AEAT-hosted
surfaces.

Remote IVA evidence must be stored through active-profile secure storage using
runtime-owned repositories. Reload APIs may read persisted evidence without a
live login. Persisted records must preserve source attribution, capture time,
redacted diagnostics, and source separation between wallet evidence,
filed-history evidence, local ledger recurrence, and explicit taxpayer
override.

Multiyear IVA compensation and pending-balance reconstruction is in scope only
when it uses production calculation/repository services and keeps AEAT evidence
as the binding external state when available. Local recurrence is diagnostic
and fallback evidence. It may not silently replace persisted AEAT evidence, and
unresolved divergence must block filing-grade output.

Modelo 130 relation-regression work is related but separate. It shares profile,
storage, source-mesh, and relation-selector infrastructure with the IVA work,
but it does not provide legal authority for IVA compensation. The Modelo 130
ADR and plan own IRPF quarterly carry-forward behavior.

Settings and external-constant centralization are part of this ADR's execution
control because live auth and Sede read drivers are not reviewable if AEAT
hosts, paths, action labels, Cl@ve waits, or test database passwords are
distributed as local literals. Existing official corpus evidence may retain
source URLs as evidence metadata; executable source-of-truth constants must
live in `Settings`, `external_constants.toml`, registry TOML/YAML, or typed
schema models.

Any future implementation slice that changes live authentication, Sede
acquisition, remote IVA evidence persistence, multiyear compensation
reconciliation, constants centralization, or related Modelo 130 coupling must
first name its governing plan row and the ADR(s) above. If no governing ADR
exists for the intended behavior, the slice is blocked until research and an
accepted ADR amendment or new ADR exists.

## Status

Accepted and in force, scoped to the wallet / profile-bucket / repository LAYER and
HIERARCHY vocabulary. Its claim to be "the binding reconciler" is SUPERSEDED (conflict
C2): the canonical authority for the SOURCE-KIND vocabulary and the cross-source
data-sourcing interface is the bindings-architecture-unification PHASE ADRs (the
phase-2.1 `binding-source-kind-taxonomy-unification` ADR for source-kind; the future
phase-2.2/2.3 ADRs for the resolver contract and the compensación carry), NOT this ADR.
This ADR remains authoritative for the layer/repository hierarchy it governs; only the
binding-reconciler over-claim is superseded. Those phase ADRs — not a central apex doc
— are the canonical direction.
