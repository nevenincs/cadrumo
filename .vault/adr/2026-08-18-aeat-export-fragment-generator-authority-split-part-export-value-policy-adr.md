---
tags:
  - '#adr'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:d07165b157caec5b19f160ba2de3e3e585319df6d1b774f1d0aba05104f2568b'
related:
  - "[[2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---

# `aeat-export-fragment-generator-authority` adr: `one semantic value written across the parts AEAT prints` | (**status:** `accepted`)

## Problem Statement

AEAT prints some quantities as a parent row subdivided into a printed `Parte
entera` row and a printed `Parte decimal` row. The record-design parser folds
that subdivision on exact tiling and the export IR descends to the LEAVES, so a
generated layout necessarily carries two fields where the declared value is one.
The export path resolves values per CASILLA, not per field, so both leaves are
handed the identical whole value and each applies its own policy to it.

No member of the closed export value-policy set selects a PART of a value, so
there is nothing correct either leaf could declare. The consequence is measured
in `2026-08-16-registry-campaign-sequencing-export-layout-authoring-backlog-audit`:
33 of 45 multi-field casillas across the published registry refuse every
realistic value, and the twelve that render write the same figure into both
halves. Every one of them sits under a structurally green tree with a valid
digest, because the generator validates anchors, coverage and digit budgets and
never renders a value.

A decision is needed now rather than later because the Modelo 347 repair is the
same shape, and re-anchoring 347 to the current precedent would copy the defect
into a second published tree instead of repairing the first.

## Considerations

- The map/parser bijection is exact and leaf-keyed; authoring a parent anchor is
  refused outright, so no authoring convention can avoid the two-field shape.
- The leaf descent is deliberate and load-bearing: it exists to stop a parent
  spanning a group and claiming reserved bytes inside it.
- The parts are not independently meaningful. One part alone cannot reconstruct
  the quantity, so a parse of one part must not present itself as the value.
- Silent truncation of precision the slot cannot hold would be an
  under-declaration written to a filing, not a formatting nicety.
- Not every printed subdivision is a split VALUE. Modelo 347 subdivides one
  printed row into a telefono and a name, which are two facts, not two parts of
  one.

## Considered options

- **Part-selecting value policies** (chosen). Two new members of the closed
  policy set, one writing the integer part and one writing the fractional
  digits, each sized by its own field's declared length. Keeps one casilla, one
  semantic value, and makes the part relationship declared data the gates can
  read.
- **Recompose the leaves back into one parent field.** Rejected: it re-admits
  exactly the parent-spanning field the leaf descent was introduced to remove,
  reopening the reserved-byte hazard for every desglose in the corpus.
- **Split the casilla so each printed part gets its own.** Rejected for parts of
  one quantity: it would fork a taxpayer-facing economic value into two wire
  artefacts and duplicate it through every calculation, aggregation and
  verification expectation that references it. Kept as the CORRECT answer for
  the other case, where the printed parts are distinct facts.
- **Express the second part as a computed field.** Rejected: the computed kind
  synthesises from a canonical producer key at export time, not from a sibling
  field's casilla; overloading it would hide the part relationship from every
  reader and every gate.

## Constraints

- The policy set is a closed core enum whose member values are the stored TOML
  tokens, so adding a member is a registry-visible schema change and needs the
  parity gate between the enum and the authored trees to stay in lock-step.
- The change is inert until the affected published trees are regenerated through
  the generator's own publication path; hand-editing a generated tree is
  forbidden, so remediation is a regenerate-and-republish, not a patch.
- No external authority is required: the wire semantics are stated by the
  designs themselves, which print the two rows, their widths, and the
  sin-signo/sin-coma-decimal convention.

## Implementation

Two members join the closed export value policy set: an integer-part policy and
a fractional-digits policy. Each is applied to the whole semantic value the
casilla carries; the field's declared length fixes how many digits that part
occupies.

The integer-part policy writes the value's integer component, zero-padded left
to the slot, and REFUSES rather than truncating when the integer component does
not fit. The fractional-digits policy writes exactly as many fractional digits
as the slot holds, and REFUSES when the value carries more fractional precision
than the slot can represent. Both stay unsigned: these designs state the
sin-signo convention, and where AEAT wants a sign it prints a separate signo
field that the layout already carries in its own right. A negative value is
refused rather than silently rendered as its magnitude.

On the parse side neither part is invertible on its own, so each parses to the
existing retained-wire-value carrier rather than presenting itself as a
reconstructed quantity. Recombination is the layout's business, not one field's.

Authoring discipline is the discriminator the considerations name: the split
pair is for parts of ONE value, and a printed subdivision carrying distinct
facts gains a casilla per fact instead. The render profile is unaffected in
shape - it continues to state one reviewed wire fact per eligible anchor, now
one per part.

The gate must RENDER rather than validate. It drives a realistic value, chosen
per declared casilla data type, through every multi-field casilla of every
published layout, and requires the concatenated part bytes to equal what the
undivided quantity would occupy across the same span. Its anti-tautology proof
is to revert one split field to the plain unsigned-integer policy and observe
the gate red.

## Rationale

The knockout criterion is that only this option can be correct at all. The
alternatives either reintroduce a hazard the pipeline deliberately closed, fork
a taxpayer-facing value into wire artefacts, or hide the relationship from the
gates - and none of them lets a filing carry the cents.

It also converts an invisible failure into declared data. Today a split pair is
indistinguishable from a duplicate mapping: both are two fields naming one
casilla, and nothing in the tree says which was meant. Once each part declares
what it writes, the pair is greppable, diffable, and checkable, and the
duplicate-mapping case becomes a distinguishable question rather than a silent
coincidence - which is what leaves the Modelo 390 entries honestly open instead
of quietly folded in.

## Consequences

Thirty-three casillas across Modelo 184's published tree become exportable for
the first time, and Modelo 347's repair becomes a re-anchoring rather than a
propagation of the defect. The date split needs no new member: the two-digit
month and day policies already exist, and that casilla simply declares
digit-string where they belong, which is now a correctable authoring error
rather than an unavoidable one.

The cost is that every affected published tree must be regenerated and
republished through the pipeline, and the campaign's "published and fully
implemented" claims must be re-read as structural until the render gate passes
over them. That re-reading is the point: a tree that validates and cannot write
a value was never finished, and the new gate is what stops the same claim being
made again.

The pathway it opens is a value-rendering gate over the whole published corpus,
not just the split pairs. The pitfall it does not close is the inverse case -
two fields naming one casilla because a map genuinely repeated itself. The gate
will now surface those as unclassified rather than resolve them, and each needs
its design read.
