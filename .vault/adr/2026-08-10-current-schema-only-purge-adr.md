---
tags:
  - '#adr'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5d244713d61e6df200f27b0c820b6460b91994d156967ed896a095f960a5b3b1'
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


## Amendment (2026-08-10): the M303 disposition screen has no boundary to sit on

### What is withdrawn

Implementation states: "The Modelo 303 observation boundary refuses a write whose
resolved typed result disposition is absent." That ruling was implemented twice,
on two different predicates, and removed twice -- the second removal at
`e593649b4f`. Both attempts broke roughly thirty-seven to forty legitimate
callers.

**The intent survives and the LOCATION is withdrawn.** An official, carry-capable
Modelo 303 observation persisted with no resolved disposition is still
under-declaration. What this record got wrong is that it named a boundary, and
the thing it named is not one.

### An earlier version of this amendment was itself wrong, and the reason is the finding

The first correction offered here was that the requirement is already enforced at
the only production routes that write M303 observations, so only a future bypass
remained. **That is true and it is irrelevant, and it is withdrawn rather than
amended.** The interesting callers of the normalisation path are not writers.

The reason the first census missed them is worth stating, because a later reader
will otherwise assume it was careless. It was not. It searched for
`normalize_m303_carry=` -- the persistence door's FLAG. Every caller that passes
the flag reaches the transform through the door; every caller that calls the
transform directly does not. The search was therefore structurally incapable of
returning a non-flag caller, it returned only writers, and "the callers are
writers" was read off it. **A pattern whose form encoded its own answer.** It was
precise, and it answered a question nobody had asked.

### The measured population, confirmed independently at HEAD

Searching for the transform functions rather than the flag:

| role | site |
| --- | --- |
| produces, through the door's flag | `live/_filed_observation_persistence.py` |
| produces, through the door's flag | `modelo/_filed_revision_observation.py` |
| asserts it was already produced | `calculations/_iva_compensation_history.py` |
| asserts it was already produced | `calculations/_iva_compensation_annual_partition.py`, two sites |
| asserts it was already produced | `modelo/_iva_wallet_gate.py` |

Four assert-sites across three modules, against two producers. **Readers and a
gate outnumber writers on that path.** One candidate fifth direct caller was
checked and dismissed: the `normalize` call inside
`calculations/_observations_repository.py` IS the door's own implementation of
its flag, not a caller bypassing it.

### The assert side uses normalisation as an oracle, and consumes nothing

`validate_normalized_m303_carry_observation_envelope` recomputes the normalised
envelope, compares it against the one it was handed, raises on difference, and
returns **the original**. It is a fixed-point assertion over the transform. None
of the four assert-sites consumes a normalised value, so the assert side needs no
normalisation capability at all -- it needs a guarantee about what it was given.

### Both candidate homes are now measured out

- **The wide persistence door** is a shared primitive with fourteen direct call
  sites: every modelo, every source kind, and the fixtures that need an
  observation to exist. A roundtrip test uses it to prove a record survives; a
  parity test to seed readers contracted to agree. Neither is filing anything.
- **The gated ingress**, one layer in, is a shared NORMALISATION path that two
  writers, three readers and a gate all pass through. Moving the screen there
  repeats the move that failed, one layer deeper.

So the amendment does not relocate the screen. **Placement is the open question**,
and these are the two excluded candidates with the evidence that excludes them.

### The invariant that explains both failures

The first attempt keyed on the resolved disposition, the second on the
declaration-type header. Neither separates a filing from a persistence proof,
**because the payloads are identical -- the difference is why the caller is
writing.** The distinguishing fact is a property of the CALLER, not of the
payload, so no predicate at either boundary could ever have separated them.

That now has three independent demonstrations rather than one: test scaffolding
at the wide door, a production READ path at the ingress, and a gate. The second
and third are stronger than the first, because they are production.

### Root cause of the over-scope

`M303_COMPENSATION_RESULTADO_CASILLA` resolves to `iva.resultado`, the ordinary
statutory Modelo 303 result box. A frozenset of four Spanish domain nouns read as
a narrow "carry casilla" set and meant "is an M303 observation" from the moment it
was written. Two rounds of narrowing then reasoned inside a scope that was never
narrow.

### Constraints on any eventual gate

**Do not key it on Modelo 303 by name.** A requirement correct for filings and
wrong for readers is a PLACEMENT error, and naming the modelo hides that. Write
the property -- a production caller of the shared door either does not write
official-source-kind observations or passes the ingress -- and let M303 fall out.
If M303-only is the right scope, that must be a measured conclusion rather than
the starting shape.

**A clarification that keeps this constraint from being misread.**
`validate_normalized_m303_carry_observation_envelope` refuses a non-M303 envelope
at its own boundary, so it is keyed on M303 by name today. That is correct: it is
a carry-specific transform and the modelo is its subject. The constraint binds the
GATE being designed, never this function. Without the distinction a later reader
would take the constraint as condemning code that is right.

**Re-check the sibling repositories rather than inheriting their exclusion.**
Retenciones and percepciones were out of scope for the M303 question. They have
their own `save_observation`, their own payload models, and a `source_kind`
documented as capture provenance -- a free-form ingestion-path name -- rather than
the official/unofficial taxonomy. That is a stated reason and it holds; it is
recorded here so the exclusion does not survive by having survived a previous
question.

### The residual exposure, and why it needs a row rather than a sentence

Nothing stops a NEW production caller using the wide door without the ingress, and
nobody would notice. That is a future bypass, not a live hole. **Recording
"already enforced" without opening the row that keeps it enforced would turn this
amendment into an argument for doing nothing about a gap that reappears the first
time someone adds a caller.** The mechanism is static rather than runtime, because
"is this a filing path" is available at the CALL SITE where it was never available
in the payload -- so the gate constrains authors, not payloads, and costs the test
corpus nothing. That inversion is what both runtime attempts were missing.

### A separate defect surfaced by this work, recorded rather than folded in

`modelo/_iva_wallet_gate.py` catches the carry-ingress refusal and returns `None`.
Three of the four assert-sites propagate it; this one does not. A carry envelope
this build cannot interpret therefore reaches that gate as ABSENT EVIDENCE rather
than as a refusal, on the compensación path, where the visible consequence is a
taxpayer's carried credit silently going unseen. It is not caused by this
amendment and is not fixed by it. It needs its own owner.

### Implementing rows

This amendment rules on code and is not self-executing. The campaign plan's `S27`
carries the red prorrata test with its close condition set to this amendment
landing, and `S28` carries the normalisation-path characterisation with the direct
callers named. Two rows open with this amendment: one to place the static
author-facing gate once placement is decided, and one to own the wallet-gate
swallow above. Neither may be closed by asserting that this record says the gate
exists.

