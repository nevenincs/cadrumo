---
tags:
  - '#adr'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:09f8091338f40e66439e69edf6a8781ee3f863d468f2a08be6d70830317fd0fa'
related:
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - '[[2026-08-07-aeat-design-relayout-boundary-research]]'
---
# `aeat-design-relayout-boundary` adr: `Modelo 200 partitions by inheritance, and 2024-y-siguientes narrows to 2024` | (**status:** `accepted`)

## Problem Statement

The accepted boundary record authorises splitting revisions that span an AEAT
design re-layout, and Modelo 200 is one of them: a single revision named
`2024-y-siguientes` serves filing years 2024 onward while AEAT published
materially different designs for 2024 and 2025. Its shipped content is the 2025
design, evidenced by casilla fragments citing the 2025 record-design source, so
a 2024 filing is currently computed against the wrong year's layout.

The boundary record authorises the split but does not say how a partition of
this size is authored. Modelo 200 is the largest form in the registry, and the
naive reading of "split it" implies re-deriving several thousand casillas from
the published design. That reading is what this record rejects.

A decision is needed now because the partition is otherwise unauthorable
without either guessing the derivation rules or hand-authoring at a volume
nobody would review.

## Considerations

- The revision's own fragments cite the 2025 design as their source while the
  revision covers 2024 onward; the mismatch is declared in the data, not inferred.
- A round-trip that re-derives the shipped 2025 casillas from the 2025 design
  reproduces most of the export mapping but leaves a stable residue of
  exceptions with three unrelated causes; derivation is therefore not a
  mechanism that can be trusted unattended at this scale.
- Several design records carry no registry coverage at all. Those blocks are
  deliberately unmodelled, and a derivation pass cannot distinguish "unmodelled
  on purpose" from "missing".
- The fields that carry meaning rather than structure - section, semantic role,
  legal grounding - vary too widely across casillas to be inferred from the
  published design, but are identical between the two years for any box present
  in both.
- The revision identifier appears many thousands of times inside the modelo's
  own tree and the same identifier string is used by other modelos, so renaming
  it is a large and easily over-matched sweep.
- Blanket working-tree commits run continuously in this repository and have been
  observed splitting an atomic registry change, so a partition that is invalid
  when half-landed carries real risk rather than theoretical risk.

## Considered options

**Re-derive every casilla from the published design.** Rejected. The
regeneration residue has three distinct causes and clearing it requires
adjudicating a set of exceptions against page semantics - tax-domain work, not
mechanism. It also cannot see which design blocks are deliberately unmodelled,
so it would invent coverage the registry has consciously declined.

**Hand-author the 2024 revision.** Rejected on volume. Thousands of casillas
authored by hand is unreviewable, and most of the work would reproduce content
that already exists correctly one revision away.

**Inherit from the sibling year, author only the difference.** Chosen. A box
present in both years copies its sibling casilla wholesale; only boxes unique to
2024 are authored.

**Rename the revision so each identifier names its epoch.** Rejected as a
separate, larger change. It touches every fragment in the modelo and risks
over-matching other modelos that share the identifier string.

## Constraints

The parent boundary record is accepted and stable, and the companion sub-year
epoch record supplies the period-token partition mechanism. Neither is in
flux, so this record depends on settled parents.

The partition must land as ONE commit. A revision carrying a partial casilla
set fails registry validation, and narrowing the existing revision before the
new one exists leaves a filing year unresolvable. Half-landed is not a degraded
state here; it is a tree-wide refusal to load.

That constraint collides with the observed blanket-commit behaviour, so the
partition must be built outside the tree and validated against a temporary
registry root before any file is written under the package. This is a
sequencing constraint on the implementation, not a reason to reshape the
decision.

The exception residue from the rejected derivation approach is NOT a blocker
for this record, because inheritance never consults the design for a box that
exists in both years. It remains an open question for whoever owns Modelo 200
export completeness, and it should not be folded into the partition.

## Implementation

The existing revision keeps its identifier and narrows to filing year 2024
alone, with its content corrected to the 2024 design: boxes absent from that
design are dropped, boxes unique to it are authored, and the record-design
source reference is re-pointed at the 2024 entry. A new sibling revision
receives today's content unchanged and serves 2025 onward.

Keeping the identifier is what avoids the rename sweep. It is also honest: the
name already says 2024, so narrowing it to mean 2024 alone makes the name true
rather than stale.

Inheritance copies the whole casilla, not a chosen subset of fields. Copying
selectively would reintroduce the derivation problem one field at a time, and
the fields most at risk - section, semantic role, legal grounding - are exactly
the ones that cannot be inferred.

Authoring is confined to boxes with no sibling in the later year, and to those
only after excluding boxes that sit on design records the registry does not
model. Both sets are enumerable mechanically before authoring starts, so the
human volume is known in advance rather than discovered during the work.

The split completes only when the progress control that pins the known
spanning revisions is updated to drop this modelo. That control exists so a
partition cannot silence the boundary detector instead of satisfying it, and
its update is part of the same commit.

## Rationale

Inheritance wins on a knockout criterion rather than a balance of merits: the
two years agree on the overwhelming majority of boxes, and for every one of
those the correct content already exists and has been reviewed. Derivation
would recompute that content and, on a measured residue, recompute it wrongly.
Choosing derivation means accepting a known error rate in exchange for nothing.

The residue also decomposes into causes with different owners - deliberately
unmodelled blocks, a genuine open question about repeated placements, and an
extraction artefact. Only the second is a registry question at all. A mechanism
that forces all three to be adjudicated before a partition can proceed has
coupled the split to unrelated work.

Keeping the identifier is chosen for blast radius, but it survives the honesty
test independently, which is why it is not merely expedient.

## Consequences

The partition becomes reviewable. The inherited majority is a mechanical copy
that a reviewer can verify by sampling, and attention concentrates on the small
authored set where judgement was actually exercised.

The human cost is now known before the work starts rather than discovered
during it, which is the difference between a schedulable task and an open-ended
one.

Two things get harder. The revision identifiers no longer read as a clean
sequence, since one names a single year and its sibling names a range; anyone
reading the tree must consult the period selector rather than trusting the
name. And the inherited casillas carry their grounding forward unexamined - if
a legal reference was wrong in the later year, inheritance propagates it into
the earlier one rather than catching it. Inheritance preserves correctness and
errors equally.

The rejected export-mapping residue stays open and now has a home: it is a
Modelo 200 completeness question, not a partition question, and folding it in
here would have hidden it inside a large mechanical change.

This record establishes a pattern the remaining partitions can follow. Where
two adjacent revisions of one form largely agree, inherit and author the
difference; reach for derivation only where no sibling exists.
