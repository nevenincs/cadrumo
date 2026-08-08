---
tags:
  - '#adr'
  - '#rate-box-evidence-assertion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:48836109c8d4d509597ec6626bbc181db5381169b71314dbb3620d805d2e18d3'
related:
  - "[[2026-08-07-rate-box-evidence-assertion-adr]]"
  - '[[2026-08-07-rate-box-evidence-assertion-research]]'
---
# `rate-box-evidence-assertion` adr: `A merged tier casilla is retired when its rungs are wired, never left as a second writer` | (**status:** `accepted`)

## Problem Statement

The parent record rules that an official box asserts only what the evidence
determines, and authorises the two-layer rate-box shape. It does not say what
becomes of the casillas that were writing those boxes before the rungs existed.

Modelo 390's recargo de equivalencia block is the live case. Three casillas
carrying tier-merged sums own the export fields for boxes the design labels with
single rates, while six correctly rate-split casillas compute and reach no byte
of the fichero. So a merged figure is filed into a slot whose printed label
names one rate, and the arithmetic is self-incriminating: the box declares its
own rate, so dividing the declared cuota by its paired base contradicts the
label.

Wiring the rungs fixes the starvation. It does not answer whether the merged
casillas then disappear, and leaving that unanswered risks the worse outcome -
two writers for one official box, with the merged one silently winning by
offset.

A decision is needed before the Modelo 390 partition, because the partition is
when these casillas are next touched and an unruled question will be resolved
by whoever is holding the file.

## Considerations

- The published design pairs every recargo cuota box with a base box and gives
  the merged concept no box of its own; there is no slot the merged casillas
  could legitimately occupy once the rungs are wired.
- The merged casillas carry a dotted identifier in the field that is supposed to
  hold an official box number, which is exactly why every box-keyed gate was
  blind to them. A gate now detects that shape, so the defect cannot recur
  silently, but detection is not resolution.
- Deleting an exported casilla is not a step to take on inference: something may
  consume it that a registry sweep does not see, as an earlier finding on a
  second delivery channel demonstrated for a different figure.
- The block is short of more than the merge. The design declares seven rungs
  where the registry models six, and pairs every cuota with a base where the
  registry models no bases at all.
- The revision holding all of this is the one under active partition, so any
  change here competes with that work for the same files.

## Considered options

**Keep the merged casillas and let the rungs write alongside them.** Rejected
outright. Two writers for one official box is the current defect with extra
steps, and the merged writer wins by offset, so the visible symptom would not
even change.

**Keep them as internal intermediates, unexported.** Rejected. The registry has
a declared way to say "computed but not filed", and using it here would preserve
a quantity the design does not recognise, inviting a future author to re-export
it. The merged sum is not a concept the return has; it was an artefact of not
having the rungs.

**Delete them in the same change that wires the rungs.** Chosen, with a
consumer sweep as a precondition rather than an assumption.

**Delete them now, ahead of the rungs.** Rejected on sequencing. It would strip
the only writer those boxes have and file blanks where a wrong-but-present
figure stands today, turning a mis-declaration into an omission.

## Constraints

The parent rate-box record is accepted, and the precondition amendment it
needed has landed, so this record builds on a settled decision rather than a
moving one.

Sequencing is the binding constraint. The revision holding the recargo block is
under active partition, and authoring export fields into it is the hazard the
partition sequencing record names. This retirement therefore rides with the
partition rather than preceding it.

Retirement and wiring must be one change. Splitting them produces either two
writers or a blank box, and both are worse than today's single wrong figure.

The design read that establishes the seven-rung shape does not carry backwards:
the rate label column does not exist in the older designs. So this record
governs the epochs where the design states rates, and says nothing about
earlier ones.

## Implementation

The wiring and the retirement are one commit: each rung's casilla gains the
export reference for its own labelled box, and the merged casillas are removed
in the same change. Between those two states there is no intermediate worth
shipping.

Deletion is gated on a consumer sweep that looks past the registry - bindings,
formulas, verification expectations, application projections and the workbook
transports - because an earlier finding established that a figure can reach an
operator surface through a channel a casilla-level sweep does not see. If the
sweep finds a consumer, that consumer is migrated to the rung it actually means
before anything is removed.

The two shortfalls the design read exposed are in scope for the same pass but
are separate work: the missing seventh rung, and the base boxes the design
pairs with every cuota where the registry models none. Wiring six rungs into a
seven-rung block would leave a slot silently blank, which is the failure this
whole family exists to prevent.

The structural detector that now sees fed-alias-beside-starved-box carries a
pinned entry for each of these pairings. Removing an entry is part of the
change, and the detector failing with a stale pin is the intended signal that
the fix landed.

## Rationale

The knockout is that the design gives the merged concept no box. A casilla
whose value has no slot in the official return is not a quantity the return
recognises; it existed only because the rungs did not. Keeping it in any form
preserves an artefact of the gap rather than a fact about the tax.

Retiring rather than internalising also removes the recurrence path. An
unexported casilla with a plausible name is an invitation: a future author
looking for something to write into a total finds it, and the merge returns by
a different route. Deletion closes that.

The consumer sweep is a precondition rather than a formality because this
codebase has already produced one counter-example to the assumption that
registry references are the whole story.

## Consequences

The filed artefact stops contradicting itself. A recargo cuota lands in the box
whose printed rate produced it, so the arithmetic check AEAT can run against
the paired base agrees rather than exposing a merge.

The change is larger than it first appears, and honestly so: six rungs wired,
three casillas deleted, a seventh rung authored, and seven base boxes modelled.
Framing it as "wire the rungs" would understate it, and a partial pass would
ship a block that is differently wrong.

There is a real risk the consumer sweep misses a channel, the same class of
miss this codebase has recorded before. The mitigation is that the sweep is
declared a precondition with a named scope rather than an assumption, so a miss
is a failure of execution against a stated bar rather than an unexamined
assumption.

Nothing here governs the pre-label epochs. Their recargo blocks remain
unadjudicated, and a future reader should not read this record as having
cleared them.
