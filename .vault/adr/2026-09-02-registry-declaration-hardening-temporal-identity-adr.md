---
tags:
  - '#adr'
  - '#registry-declaration-hardening'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:08cdc3250351a6f36088814f7b35424ac1ffecaa09fcef1842505163cc7b81d7'
related:
  - "[[2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit]]"
  - "[[2026-09-02-registry-declaration-hardening-declaration-kinds-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
  - "[[2026-08-31-period-revision-resolution-ad-hoc-operation-date-axis-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
---

# `registry-declaration-hardening` adr: `A revision declares one temporal window and evidences each year it claims` | (**status:** `proposed`)

## Problem Statement

A revision states its temporal reach in eight places. The directory name carries year tokens
and is also the revision identifier, so it appears in prose, tooling output, review stamps and
every document that cites the revision. The window carries an opening date and an optional
closing one. The period selector carries its own year bounds and, separately, an explicit years
tuple. Each deadline window carries a filing year, and there are 843 of them. Source references
carry applicability windows, legal references carry effective dates, and the authorisation
manifest carries enrolled years. Three agreement validators reconcile some of these pairs after
the fact.

Measurement changed what this problem is. The sites do not contradict each other: no deadline
window anywhere names a filing year outside its revision's own window, and no period selector
carries both an explicit years tuple and a year bound. What the sites do instead is fall silent.
Twenty-seven revisions declare no deadline window at all. Nine more declare a closed window
containing years no deadline window serves, one of them spanning fourteen years and serving none
of its first seven. Fourteen revision names disagree with the window they declare, and seven of
those name a single year while the window runs open-ended, which understates reach rather than
overstating it and so attracts no attention.

Fifty-four revisions are open-ended, taking that to mean a revision declaring neither a closing date
nor a closing selector year, and twenty-eight of those are filing grade. Selecting a revision for
a filing year far beyond any evidenced year returns one of them without diagnostic, because the
registry has no way to say that a window is open until superseded but has only been verified
through a particular year. Those are different claims and the schema has one field for both.

One modelo puts a non-temporal axis in the revision slot: its three revisions are named for
schemes rather than periods, share a validity start, and are disambiguated only by period-token
namespace, with the consequence that a support matrix reports one of them as the latest on the
tie.

## Considerations

The sibling declaration-kinds decision is a prerequisite for the derivation half of this record.
Without a derived field kind, deriving selector years from the window would leave two authored
sites and simply move the problem.

An accepted decision already governs how a period resolves to a revision, and a proposed sibling
already targets the one ambiguous coordinate this campaign found. This record must not restate
either; it decides what a revision declares about its own reach, not how a caller selects one.

The fragmentation is silence rather than contradiction, and that changes which remedy works.
Stricter agreement checking finds contradictions, and there are none to find. What is needed is a
shape in which a year cannot be claimed without being either derived from the window or
evidenced on the record.

The registry already distinguishes evidence grades elsewhere and the no-silent-under-declaration
rule already requires missing, unknown, deferred, advisory and proven states to stay distinct. A
coverage record expressing asserted against verified is an application of an existing principle,
not a new one.

## Considered options

**Keep the sites and make the agreement checks strict.** Promote the advisory temporal coherence
check to a refusal and extend the name-window agreement in both directions. This is the cheapest
option and it closes the fourteen lying names. It does nothing about open-ended assertion,
nothing about the scheme axis, and nothing about the twenty-seven revisions that declare no
deadline window, because none of those is a disagreement between two statements. It leaves the
registry able to claim validity for 2035 on a 2019 design with nowhere to record that nobody has
checked.

**Declare the window once, derive the selector from it, evidence each claimed year, and give the
non-temporal axis its own field.** The window becomes the single owned temporal fact. Selector
years become derived under the declaration-kinds contract. A coverage record per revision and
horizon year carries a state of asserted, verified or superseded, so the closure report can
distinguish a year the registry merely claims from one it has evidence for. A typed axes
declaration carries regime or scheme partitions, so the revision slot holds only revisions.

**Split every open-ended revision into one directory per filing year.** This is honest by
construction and needs no new schema. It multiplies fifty-four revisions into several hundred
near-identical trees, breaks continuity chains that currently hold, and forces every cross-year
validator to enumerate far more coordinates. It replaces one fragmentation with a larger one.

## Constraints

The window is the owned fact. Every other temporal statement about the revision's own reach is
derived from it or is evidence about it, never an independent declaration of it.

Asserted and verified are different states and neither may be written as the other or as absence.
A revision with no coverage record for a year makes no claim about that year, which is itself
distinct from claiming it unverified.

Backfilling verified is only legitimate where independent evidence already exists for that year.
A deadline window and a source window that both cover the year is the minimum; everything else is
asserted. Marking a year verified because the registry currently serves it would be the engine
agreeing with itself.

The directory name is an identifier and stops being read as a temporal claim. Because it is also
the identifier used across code, tests, generated output and review stamps, correcting a
misleading name is an identifier change and moves every referencing surface atomically.

Open-ended windows are never measured against an invented horizon. A screen or gate that assumes
an end date in order to find gaps manufactures findings the declaration does not support.

## Implementation

Stage the work so each step stands alone. Add the coverage evidence record first: it is purely
additive, changes no selection behaviour, and immediately lets the closure report separate a
claimed year from an evidenced one. Add the typed axes declaration next and move the scheme-named
revisions onto it, which removes the tie that makes a support matrix pick a latest revision
arbitrarily. Derive the selector years from the window last, once the declaration-kinds contract
exists to make the authored keys refuse.

The revision name corrections are separable from all three and need operator approval before they
land, because each is an identifier change with a wide referencing surface.

The temporal site agreement screen stays and keeps reporting. Deriving the selector removes one
of its comparisons; the deadline silence it measures is data to author, not a shape a contract
can forbid.

## Rationale

Stricter agreement was rejected because measurement showed there is nothing for it to catch. Two
conditions were screened for across the whole corpus and neither occurs. A remedy aimed at
contradiction cannot address an axis whose failure mode is omission.

Per-year revisions were rejected on maintenance cost. The mandate behind this work is that
fragmentation makes the registry unmaintainable, and multiplying the revision count by an order
of magnitude is more of exactly that, however honest each individual directory would be.

The coverage record is staged first because it is the only part that improves the honesty of the
current reporting without touching selection, which is the load-bearing path. Deriving the
selector is staged last because it is the part that depends on another decision.

## Consequences

The registry gains the ability to say that a revision is open until superseded but verified only
through a stated year, which it cannot say today. The closure report stops treating the two as
the same claim.

Roughly two hundred coverage records are authored for the current horizon. Three agreement
validators become deletable once the selector is derived. The scheme-named revisions are renamed
and their generated export provenance and authorisation entries move with them.

Selection behaviour is unchanged by the first two stages and changes only when the selector is
derived, at which point the window is always consulted. That is the stage carrying real risk, and
it is deliberately last.

Fourteen revision names remain wrong until they are corrected, and this record does not correct
them. It removes the reason they were load-bearing, which is that a reader had no other statement
of reach to consult.
