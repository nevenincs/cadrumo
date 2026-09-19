---
tags:
  - '#adr'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:abafc87e373552a314c67bed3bb7d1defa17fcf876bbd3bbdec0cb6e7db311b4'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-31-tui-interface-command-path-population-measurements-reference]]"
---

# `tui-interface` adr: `path keyed evidence classification` | (**status:** `proposed`)

## Problem Statement

Several generated artefacts are keyed by source path, and every relocation
invalidates them silently: the file still parses, whatever reads it still
passes, and a symbol grep cannot see the breakage because these artefacts name
PATHS rather than symbols. Four were named together and a single fix was asked
for across all of them.

## Considerations

**They are not one population, and treating them as one produces the wrong fix
for one of them.** Measured on 2026-08-31:

- Four artefacts under the quality directory are path-keyed INVENTORIES of the
  CURRENT tree. All four are already named by a test module, and the two
  censuses carry real drift gates that re-derive and compare.
- The benchmark baseline's source manifest is a content-addressed SNAPSHOT of a
  PAST measurement, captured from a pristine checkout rather than the working
  tree.

**The worked example that prompted this row belongs to the second category, and
is not broken.** It was reported that the manifest still carries a path for a
deleted file. That is true, and it is 541 such entries out of 28,414 -- about
two percent, which is what a snapshot of a past tree looks like after ordinary
churn. It is not an overlooked entry; it is the artefact working. A shipped
gate asserts the manifest IS stale against the current tree, so "repairing" its
paths would break a test whose whole subject is that staleness, and would
rewrite a recorded observation to match today -- which is how a receipt becomes
a fabrication.

**So the real residual risk is not path fragility. It is enrolment.** Each
existing artefact has something watching it. Nothing watched whether the NEXT
generated artefact would, and a new one arrives looking exactly like the ones
that are covered.

## Considered options

**A. Make path keys robust** (store module identity, or a content hash, instead
of a path). Rejected for the inventories: their subject IS the set of paths, so
a key that survives relocation would hide the very change the census exists to
report. Rejected for the snapshot: its keys are a record, not a lookup.

**B. Add a drift gate to each artefact.** Already true for all four
inventories, so as a plan this is complete and as an answer it is incomplete --
it says nothing about the fifth artefact nobody has generated yet.

**C. Classify each artefact, then gate by class, and gate the CLASSIFICATION
itself.** Inventories get a detector that re-derives from the tree and
compares. Snapshots get the opposite guarantee: never hand-edited, expected to
diverge, and asserted stale. The single shared mechanism is not a path scheme
but the requirement that every generated evidence artefact be enrolled with
something that notices it rotting.

## Implementation

C, and its enrolment half has landed: a gate asserts that every generated
evidence file under the quality directory is named by some test module, with
the snapshot deliberately excluded and the exclusion carrying its reason. It
checks ENROLMENT rather than freshness -- whether a detector exists, not
whether it is any good -- because a weak detector and no detector fail
differently and only the second is invisible.

The gate carries a proof that its own predicate can fail. That probe's name is
assembled at runtime rather than written as a literal, because the search reads
test sources and the gate is one of them: spelled plainly, the module would
find its own text and report enrolment for a name nothing generates.

## Rationale

Asking for "one answer across all four" assumed the four share a failure mode.
They share a KEY TYPE. Once the two categories are separated, three of the four
questions were already answered and the fourth -- what happens to the next
artefact -- was the only one open.

## Consequences

The operator question the row raised, whether the benchmark manifest may be
edited without re-capturing, is answered NO by classification rather than left
open: it is a measurement record, and the only honest way to make it current is
a fresh capture. No decision is needed to leave it alone.

An artefact that is genuinely retired now fails this gate until it is deleted,
which is the intended pressure: a generated file nothing reads is not evidence.
