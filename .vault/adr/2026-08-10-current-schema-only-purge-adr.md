---
tags:
  - '#adr'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:76921e3b660c0b5f4cb24b223adbf2d99f1760f58a82492893e34c2e3aad95cc'
related:
  - "[[2026-07-09-compatibility-lifecycle-adr]]"
  - "[[2026-05-06-secure-persistence-enforcement-adr]]"
  - "[[2026-06-10-zero-legacy-purge-research]]"
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# `current-schema-only-purge` adr: `current-schema-only hydration and persistence` | (**status:** `accepted`)

## Problem Statement

Two accepted decisions already govern this application's posture toward its own
older data: `2026-07-09-compatibility-lifecycle-adr` fixes the regime as
pre-release and rules that durability floors chase the current version, and
`2026-05-06-secure-persistence-enforcement-adr` rules that encrypted reads fail
closed and that schema-version mismatches are never silently accepted. Neither
is self-executing. A ruling about code is not evidence the tree obeys it, and a
grounding pass over the persistence boundaries found several that hydrate a
non-current shape without refusing.

What is missing is not another statement of the posture. It is a record of the
adjudication: which concrete tolerances in this tree are legacy support to be
deleted, and which superficially identical surfaces are forward-functional and
must survive the sweep. Without that boundary written down, each deletion is
adjudicated ad hoc by whoever holds the file, and the failure mode is
asymmetric -- deleting a forward-compatibility ceiling or a fresh-schema
bootstrap is a regression that looks like progress, and on the key-management
boundary it can strand encrypted data outright. An implementation plan for this
purge exists and is in flight; it was authored without this record, which is
the defect this ADR closes rather than a formality it satisfies.


## Considerations

- The pre-release regime is a property of the codebase commit, not the
  environment; `2026-07-09-compatibility-lifecycle-adr` establishes it and
  blesses forward version fields and future-refusing ceilings as things to KEEP.
- Fail-closed encrypted parsing is already required; the open question is
  ORDER, since a refusal that fires after key derivation has already used the
  key it was meant to guard.
- `2026-06-10-zero-legacy-purge-research` carries the prior campaign's inventory
  and the owner rulings that closed it, including the distinction that AEAT
  regulatory status is never evidence of code legacy.
- Measured during this campaign's grounding pass, and not carried by that
  inventory: the dominant tolerance shape in this tree is not a branch on an old
  version. It is a pydantic DEFAULT on the version marker itself. A payload that
  omits the marker hydrates as current, so an equality gate placed downstream
  never fires and reads as enforcement while enforcing nothing. The same shape
  recurs across the outer cipher envelope, the secret-store index, the wrapped
  master key, the file-fallback KDF record and the live profile aggregate.
- Version marking has no single canonical home. Four independent conventions
  coexist: a per-model field validator, one shared identity validator, a module
  constant compared inline, and the secure-object lineage ceiling. This purge
  tightens each in place; it does not attempt the consolidation, which is a
  separate decision.

## Considered options

- **Delete the version markers and rely on strict models alone.** Rejected: it
  destroys the forward-compatibility the governing lifecycle decision requires
  kept, and a strict model cannot tell a current payload from a future one.
- **Keep a ceiling and add a floor, accepting a supported range.** Rejected: a
  range is read-tolerance renamed. Pre-release there is no released shape
  entitled to interpretation, so the supported range has exactly one member.
- **Make every marker a required field with no default, sweeping every
  construction site.** Rejected as a universal rule, on measurement: the live
  profile aggregate alone has 231 construction sites across roughly 150 files,
  all but two of them tests and development harnesses owned by other campaigns.
  Retained as the correct end state per boundary where that cost is bounded, and
  carried as its own row rather than smuggled into a validator change.
- **Chosen -- exact equality against the authority's declared current version at
  every persisted boundary, with the marker written explicitly and the refusal
  placed before any cryptographic use.** Defaults are derived from the declaring
  authority rather than inlined as literals, so a schema advance moves behaviour
  without a sweep.

## Constraints

- Key management is owner-gated. Deleting a key-schedule or DEK-derivation
  branch, or removing the default on a key-schedule discriminator, can render
  existing encrypted buckets unreadable. Two rows of the in-flight plan are
  refused pending an operator ruling rather than decided by the implementing
  agent; that refusal is part of this decision, not a delay in executing it.
- Territory is shared. Workflow action-detail compatibility is owned by a
  separate in-flight campaign and is explicitly out of scope here, and the core
  package is held by a concurrent relocation.
- Verification is incomplete by construction in this environment. The eight
  cases asserting that a profile data-encryption key is custodied in the OS
  credential store and unwrapped by a later process carry a marker no test lane
  reaches, and the capability is a property of the interactive logon session
  rather than of the dependency set. Those assertions are recorded as a known
  unverified surface; a green run elsewhere does not stand in for them.

## Implementation

The tightening is layered, and each layer keeps its own authority rather than
routing through a new shared one.

Domain records pin schema identity through the single validator both the live
aggregate and the immutable snapshot already share, so one change covers both
and no second authority appears. The plaintext active-profile pointer pins its
own document marker at the parse boundary. Catalogue models drop the arm that
wraps a bare mapping into the canonical container, so a payload written without
that container refuses through the module's existing typed error instead of
hydrating as valid; the explicit construction API and its duplicate-identifier
refusal are preserved.

Encrypted wrappers require their format claim explicitly and refuse BEFORE the
master key is consulted, which is the ordering the governing persistence
decision implies but does not currently obtain everywhere. Local custody
metadata -- the secret-store index, the KDF parameter record, the bucket
manifest key schedule -- requires its current marker on every read and writes it
on every write. The Modelo 303 observation boundary refuses a write whose
resolved typed result disposition is absent, delegating to the existing
determined-fact resolver rather than re-deriving the value at the write site.

Every boundary tightened carries a strict round trip through real adapters --
real key provider, real database engine, real serializer -- with every
defaultable field populated to a non-default value, paired with an
anti-tautology proof that mutates the stored payload to remove the field and
asserts refusal on reload.

## Rationale

Exact equality wins on a knockout criterion the alternatives cannot meet: it is
the only option under which the two failure directions refuse alike. A ceiling
refuses a future payload while accepting every pre-current one, and the
pre-current direction is the more dangerous of the two because it produces a
plausible record rather than an error. On a pre-release codebase with no
released data, nothing is entitled to write a pre-current shape, so accepting
one can only mean corruption or a defect in this application -- neither of which
is served by silent interpretation.

Placing the refusal before key derivation follows from the same reasoning
applied to ordering: a format claim is the cheapest thing to check and the
earliest thing available, and checking it after the key has been derived spends
the secret the check exists to protect.

Deriving defaults from the declaring authority rather than inlining literals is
what keeps the decision from decaying. A literal current version at a call site
is a second authority that goes stale the moment the schema advances, and the
form that failure takes is silent.

## Consequences

- Good: a payload that is not exactly current refuses at the boundary that owns
  it, in both directions, with a message naming the claimed version and the
  canonical one, so the refusal is actionable rather than merely safe.
- Good: the scope boundary is written down and ratifiable. Empty upgrader
  registries, regime gates, durability-floor checks and future-version refusal
  scaffolds are KEPT -- they read no obsolete shape. Fresh-schema creation on
  first access is KEPT; an ALTER pass upgrading an older table is not. AEAT
  regulatory revisions and external-source variability are KEPT and are not
  reinterpreted as this application's legacy: each filing year's revision is
  current law for that year.
- Accepted cost, stated rather than discovered later: this decision does not
  close the omitted-marker case everywhere. Where a marker still carries a
  default, a payload omitting it hydrates as current. Closing that requires
  required-ness plus a construction-site sweep, and it is tracked as its own row
  because an unowned prerequisite is how a campaign closes with its goal open.
- Accepted cost: two key-management rows stay unexecuted pending an operator
  ruling, so the custody metadata boundary is tightened only in part. Deleting a
  key-schedule or DEK-derivation branch can strand encrypted data, which is a
  decision this record deliberately does not take.
- Accepted cost: the four coexisting version-marking conventions survive this
  purge. Their survival is NOT an endorsement of the fragmentation. Consolidating
  them onto one authority is a larger decision that was not taken here, and a
  later reader should treat the four as an open question rather than as a settled
  arrangement this record ratified.

