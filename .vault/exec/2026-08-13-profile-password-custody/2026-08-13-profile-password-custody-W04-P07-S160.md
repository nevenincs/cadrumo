---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3e5038b04e66706ea318425ec70df174d866291fa2983f7006701dc6899d64bd'
step_id: 'S160'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make a persisted format declaring its current version in more than one place mechanically detectable, since the fincas five and the portable export bundle were each found by reading rather than by any gate, and a second literal that silently disagrees with the first is exactly the drift the durability inventory exists to prevent

## Scope

- `src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Read both repaired instances to extract the shapes a detector must catch.
- Gate the enabling property -- no version field authors its own number -- with a stated standing inventory.
- Prove the gate bites on a real format from outside the repository.

## Outcome

**Verdict: shipped as a production-surface AST gate asserting that a
version-bearing field never authors its own number.** It either carries no
default, so the writer stamps the version from the constant that owns it, or its
default references that constant by name. A literal in that position is one of
exactly two things and both are the defect: a SECOND declaration when a constant
already exists, or the SOLE declaration, unnamed -- and the unnamed case is
worse, because a name is what makes any future second declaration comparable at
all.

**That framing is what makes both fixtures catchable by one property.** The
portable export bundle held a named constant beside a model default carrying the
same number: a second declaration. The five rental-register shapes held the
number once on the domain model and once again as a column default, with no name
on either side: two sole declarations that could disagree with nothing to
compare them. A same-module duplication rule would have caught the first and
missed the second entirely. Gating the enabling property catches both, and it
states the consequence honestly -- once no field authors its own number, every
declaration of a format's current version is a NAME, and two names for one
format are visible to the enrolment gate that discovers formats by constant
name.

**The blind spot question, answered directly: it does NOT share the
named-constant blind spot.** The enrolment gate discovers formats by constant
name, so a version that never got a name is invisible to it. This one discovers
by FIELD name, so it sees exactly those shapes -- which is why the rental
registers, invisible to the other gate for their whole life, are the case it was
built from. Its own blind spots are different and are written into the module:
a version field spelled something other than `schema_version`; a number restated
in prose, where nothing compiles the claim; a type-constraint restatement, which
is real but fails loudly at the next construction rather than silently; and two
named constants for one format in two modules, which is the other gate's axis
and only becomes visible once this property holds.

**No count is asserted anywhere.** The gate fails on the PROPERTY. The
twenty-three sites standing when it landed are recorded as a table keyed by
path, enclosing class and field -- never by line number -- each carrying a
stated reason, and a stale entry fails its own test the moment it stops naming a
live site. The table is deliberately not called an allowlist: it classifies each
standing site into one of three shapes, and only one of those shapes is arguably
fine as it stands.

**It found two live instances on its first run, both by mechanism rather than by
reading.** A remote-mirror namespace manifest carries a model default holding the
same number its sibling module's constant declares, which both the builder and
the version check already bind -- the rental-register shape exactly, still
standing. And one custody owner receipt writes a bare literal in a module that
declares the very constant for it, with its two sibling records in that same
module already binding it, so that field is the odd one out rather than the
convention.

**Bite proof, from outside the repository.** A scratchpad script feeds the gate
the real production surface with one module's AST replaced by an in-memory
mutation of that same real source -- a second, DISAGREEING literal reintroduced
for the portable export bundle, whose constant says three and whose injected
default says two. Baseline: no unclassified site. Mutated: exactly one offender,
naming the injected site. A third arm drops one real standing site from the
surface and confirms the stale-entry test reports its table entry. Nothing under
the source tree was written at any point, so no peer sweep could capture a
mutation.

## Notes

Twenty-three standing sites rather than zero, and the shape of that number
is worth stating: none of them is in this record's own ownership, so the gate
lands describing defects it cannot itself repair. Three classes are recorded --
a dead second declaration beside an existing constant, an unnamed sole
declaration on a format nobody has classified, and a response-contract version
that is not the durability inventory's subject at all.

The detector was written to accept string versions as well as integer ones. That
is not generality for its own sake: the rental registers version with strings,
so a detector seeing only the integer spelling would have missed one of the two
cases it exists for.

A pre-existing lint finding sits in one of the files touched here -- a
suppression comment for a rule the configuration no longer enables. It predates
this work and was left rather than swept.
