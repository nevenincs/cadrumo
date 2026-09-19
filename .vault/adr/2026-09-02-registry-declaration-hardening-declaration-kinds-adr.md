---
tags:
  - '#adr'
  - '#registry-declaration-hardening'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:fac385a00d8607e02206b588f25ddc6627262f5a441112451f7cd5813d7a47e6'
related:
  - "[[2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit]]"
  - "[[2026-09-02-registry-declaration-hardening-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
---

# `registry-declaration-hardening` adr: `Every registry field is owned, derived, or attesting` | (**status:** `proposed`)

## Problem Statement

The registry lets the same fact be written in several places and then spends a great deal of
machinery noticing when the copies disagree. A revision's temporal reach is stated at eight
sites, reconciled afterwards by three agreement validators. One citation can be restated at
eleven sites. A casilla's numeric identifier is restated as a separate number field on all
29522 rows. The casilla-to-export-field edge is declared from both ends. Fifty-one validator
modules exist across the registry package, and a large share of their work is reconciliation
rather than validation.

Every additional site is somewhere a maintainer can omit, contradict, or silently drift, and
the reconciliation is detective rather than preventive: a contradiction is authorable, gets
written, and is caught later by a test if a test happens to exist. Measurement during this
campaign found conditions where no test existed at all, and found four separate published
figures that were wrong because a consumer reassembled a derived surface by hand instead of
asking for it.

The question this record decides is not which validators to add. It is whether the registry
keeps a shape in which restatement is possible and policed, or moves to one in which
restatement cannot be written down.

## Considerations

The project's quality rule already prefers a contract that is unconstructable to violate over
one asserted in a test, and its architecture rule already requires one canonical definition per
symbol. This decision applies both to data declarations rather than to code.

The registry schema already carries field markers of exactly this kind, distinguishing
manifest-only fields, schema families and governance stamps. The mechanism to attach a
classification to a field therefore exists and does not need inventing.

A derived surface with a canonical accessor already exists as a worked example. The resolved
export surface is now returned whole by one function in the registry export module, and the
consumers that previously each rebuilt it from three linkage paths now ask for it. That change
removed a class of defect rather than detecting instances of it, which is the shape this record
generalises.

Validation runs in two regimes, and a warm load skips registry validation entirely through a
persisted verdict token. Any enforcement this record installs must therefore sit where it
demonstrably executes on a contributor machine, which means the loader rather than a validator
module.

## Considered options

**Keep every site and add the missing agreement checks.** Eight screens now measure the
conditions the audit named, and four of them are precisely the checks this option would
install. It needs no data migration and no loader change. It also leaves every cause in place:
the validator count keeps growing, a maintainer can still author a contradiction, and the
registry stays a structure whose correctness is a property of its tests rather than of itself.

**Classify every field as owned, derived, or attesting, and refuse an authored value for a
derived field at load.** Owned means the fact is authored once at the entity that owns it.
Derived means one named function computes it and the loader refuses any authored key for it.
Attesting means the field is an evidence record pointing at an owned fact, never a copy of it.
This extends the existing marker mechanism, migrates one field at a time, and leaves consumers
unchanged because a derived attribute keeps its name and type. Its first applications delete
more code than they add.

**Separate the authored model from a derived projection type.** Keep authored models pure and
expose a second resolved type carrying every derived field. This is the cleanest separation and
the most expensive: the registry exposes one snapshot type that consumers depend on throughout,
and every one of them would change type.

## Constraints

A derived field must be computed by exactly one named function, and that function is its
canonical definition. Two functions computing the same derived field is the defect this record
exists to prevent, not an implementation detail.

Refusal happens at load, not in a validator module, because a warm load skips validation and an
enforcement that does not run is indistinguishable from one that always passes.

A field may not be reclassified as derived while any consumer still authors it. The migration
for one field is: add the deriving function, delete the authored key from every declaration,
flip the marker, and let refusal turn on, in one change.

Attesting fields keep the distinction between missing, unknown, deferred, advisory and proven
zero. An attestation that a fact was not checked is a different value from an attestation that
it was checked and held, and neither may be written as absence.

## Implementation

Extend the existing schema field markers with the three kinds. Teach the loader to refuse an
authored key on a field marked derived, with a message naming the field, the owning entity and
the function that computes it. Compute derived fields after load so the attribute is present
and typed for consumers.

Migrate in this order, smallest blast radius first: the period selector's year bounds and years
tuple, derived from the revision window; the calculation grade, currently derived twice by two
different predicates; the casilla number, which restates a numeric identifier; and the casilla
export references, which restate an edge the resolved surface already carries. Each is one
change that deletes an authored key, adds a function, and removes at least one agreement check.

The eight screens stay. They are how a condition is measured before it is made unrepresentable,
and several of them measure conditions no marker can fix.

## Rationale

The alternative was tried and is what exists. Fifty-one validator modules are the accumulated
result of adding a check each time a restatement went wrong, and the campaign that produced this
record found conditions with no check at all and four published figures that were wrong for
exactly that reason. Adding four more checks would have been the fifth iteration of a strategy
whose failure mode is already documented.

The loader is chosen over a validator because a warm load skips validation. An enforcement
placed where it does not run is worse than none, because it reads as protection.

The derived kind is preferred to deleting redundant fields outright because consumers depend on
the attribute names, and derivation keeps the name while removing the authoring. That is what
makes the migration incremental rather than a cut-over.

## Consequences

Restating a derived fact stops being a thing a maintainer can write. The failure moves from a
test report to the load itself, and it names the owning function.

Agreement validators become deletable as their fields are migrated, so the validator count falls
rather than grows. Three temporal agreement checks are the first candidates.

Every consumer of a migrated field is unaffected in source, but the registry declarations shrink:
128 manifests lose their selector year keys, and 29522 casilla rows lose a restated number.

The three sibling decisions depend on this one. Temporal identity, identifier grammar and
wire-type derivation each need the derived kind to exist before their own projections can be
derived rather than declared, which is why this record is taken first and why they should not be
accepted before it.

The cost is a loader change on a load-bearing path, and a migration that must be done one field
at a time with the owning tests run at each step. A partially migrated field, authored in some
declarations and derived in others, would refuse at load for some revisions and not others, so
each field's migration is atomic even though the sequence is incremental.
