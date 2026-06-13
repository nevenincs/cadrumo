---
tags:
  - '#research'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-14-profile-bucket-lifecycle-adr]]'
  - '[[2026-05-21-profile-uuid-identity-adr]]'
  - '[[2026-05-21-profile-state-aggregate-adr]]'
  - '[[2026-05-21-state-read-projection-adr]]'
---

# `live-iva-compensation-wallet` research: `profile, bucket, repository, and binding terminology reconciliation`

This research rereads the binding, secure-storage, profile lifecycle, profile
identity, profile aggregate, state projection, secure-object drift, and live IVA
wallet ADR trail to identify the vocabulary and hierarchy the wallet repair
wave must enforce.

## Findings

The accepted secure-storage trail defines a storage split: a profile is the
operator-facing tax identity, and a bucket is the encrypted storage slice. The
May 14 lifecycle ADR selected 1:1 profile to bucket cardinality, per-bucket key
material, per-bucket databases, manifest discovery, explicit switching, and a
`BucketSession` that owns unlocked key material and bucket-scoped engines.

The May 16 lifecycle CLI ADR kept the May 14 storage architecture but changed
the operator vocabulary. User-facing commands should say profile, not bucket.
The plaintext active pointer is named for the active profile on the operator
surface, while storage code may still use bucket as the implementation noun.
That ADR also resolved that list reads manifests only, show/edit/export can
default to active, and delete must never default to active.

The May 21 UUID identity ADR changes the older May 14 assumption that
`bucket_id` and profile name can be the same value. The stable identity is now
a generated UUID. The display name or label is mutable and must not appear in
keys, paths, pointer values, token filenames, or secure-object natural keys.
Command entry may resolve a label to a UUID, but every lower layer works with
the UUID.

The May 21 profile aggregate ADR adds a stronger ownership rule. A logical
profile spans manifest, pointer, encrypted profile row, bucket directory, token
and lock files, and lifecycle state. A single `ProfileRepository` owns writes
across those stores, and direct CLI or application-service writes to individual
stores are forbidden. The state projection ADR complements this on the read
side: operator-facing surfaces consume one canonical projection rather than
re-deriving profile, auth, modelo, and readiness state independently.

The secure-object drift research proves why this hierarchy matters. Default
SQL repositories can route to the active bucket or a fallback database through
settings. Tests using an ephemeral key without database isolation wrote
unreadable rows into active profile storage. Repair and calculation confidence
work therefore must treat repository routing, bucket session, and active
profile context as part of the correctness surface, not as incidental setup.

The binding ADR trail uses the word binding for modelo calculation inputs:
registry binding definitions, source-owned binding resolvers, and operator
overrides. That is a separate concept from profile or bucket binding. The
calculation source mesh ADR says the calculation engine should receive a typed
source resolution envelope and must not read ledgers, invoices, profiles, live
captures, or repositories directly. Application resolvers are responsible for
reading bucket-attached repositories and producing typed source observations.

The live IVA wallet ADR adds a second authority ladder. AEAT wallet evidence is
a read-only external observation, local recurrence is comparison and fallback,
and taxpayer override is explicit. A persisted non-blocking reconciliation
decision is the only value that may feed Modelo 303. The wallet read path must
not mutate AEAT state, and a wallet pull must not directly mutate a calculation.

The unresolved ADR-level issue is the overloaded phrase active profile. It can
mean the operator-selected label, the active pointer value, the UUID storage
identity, an unlocked `BucketSession`, the encrypted profile record, or the
canonical read projection. Those are different layers and different failure
modes. The repair privacy fixes already showed the risk: printing an active
bucket UUID as an active profile leaks an operational identifier and confuses
users.

## Reconciliation Recommendation

Adopt a binding ADR that declares the hierarchy from user intent to storage to
calculation:

1. Operator input names a profile label.
2. Label resolution selects one immutable profile UUID.
3. The profile UUID is the bucket identifier and pointer value.
4. The bucket manifest supplies non-sensitive routing metadata.
5. Unlock creates a `BucketSession`.
6. The session constructs bucket-attached repository factories.
7. Domain repositories load typed profile, ledger, invoice, wallet, filing, and
   calculation evidence.
8. Application source resolvers produce typed calculation source observations.
9. The calculation source mesh produces binding values and diagnostics.
10. Wallet and filed-history reconciliation decisions gate remote-state values.

The ADR should also reserve wording. Profile means tax identity or
operator-facing account. Profile label means mutable display name. Profile UUID
means opaque storage identity. Bucket means encrypted storage slice. Bucket
session means unlocked cryptographic and database context. Repository means a
typed domain persistence boundary attached to a bucket session. Secure object
repository means the physical encrypted store, not a domain repository.
Calculation binding means a registry/modelo source input, not a profile/bucket
attachment. Reconciliation decision means a persisted authority selection
between wallet, local recurrence, filed history, and explicit override.

The implementation consequence is that W05 repair and calculation-confidence
work must be bucket/session aware but operator-output redacted. It may report
active profile context as a redacted marker or label where the command is an
explicit profile inventory command. It must not print the UUID on repair,
diagnostic inventory, or attribution surfaces. Calculation/export surfaces must
gate on the health of the repositories used by the source resolvers they need.
