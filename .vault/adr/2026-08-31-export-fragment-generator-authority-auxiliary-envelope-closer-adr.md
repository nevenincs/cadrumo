---
tags:
  - '#adr'
  - '#export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:2bc6048fe414795338f8907bce1bb6e39b753f977abd24b878fe22927c2d4513'
related:
  - "[[2026-08-31-export-fragment-generator-authority-auxiliary-envelope-classification-research]]"
  - "[[2026-08-28-registry-narrow-mechanism-widening-adr]]"
---

# `export-fragment-generator-authority` adr: `the file closer is a field, and the aux-header branch is a spelling artifact` | (**status:** `proposed`)

## Problem Statement

Modelo 390's page-zero design prints an eighteen-byte file closer that the generated
export tree does not emit, and both published Modelo 232 trees do not emit it either. A
decision is needed because the omission concerns the bytes of a filing artifact, and
because the cheapest way to clear the red — teaching a matcher one more spelling — is the
exact remedy an accepted record already forbids.

Two questions had to be separated. Whether the closer belongs in the emitted file is a
question about AEAT's design, answerable only from AEAT's own document. How the code came
to omit it is a question about this repository, and that answer proved narrower and more
troubling than a missing feature.

## Considerations

- The closer is numbered field 15 in the sheet's own number column, which runs 1 to 15.
  It sits inside the field sequence rather than below it, and it closes the tag that
  fields 1 to 6 compose. Field 6's own description is "Tipo y cierre".
- Modelo 303's `DP30300` and Modelo 390's page zero are row-for-row identical in
  structure. Read directly from the two bundled workbooks, the only differences are
  capitalisation (`Variable` against `variable`, `Total` against `TOTAL`) and the year
  placeholder (`AAAA` against `EEEE`). Modelo 303 emits the closer today.
- `record_design_workbook.py:258` tests `raw_length == "Variable"` exactly, and `:217`
  tests the same token for the total. Neither folds case. When the body marker fails to
  register, the variable-envelope branch returns immediately and the sheet falls through
  to the auxiliary-envelope-header branch, which is closer-less and total-less by
  construction.
- Those two comparisons were cited as `record_design.py:1894` and `:1853` when this
  record was drafted. The module was split on 2026-08-31 and they now live in
  `record_design_workbook.py`, re-verified there by reading both call sites. The
  behaviour is unchanged; only the locations moved. Confirm against the live file rather
  than the line numbers, which this campaign has already moved twice.
- So the auxiliary-envelope-header shape is not a second AEAT record shape. It is the
  same envelope reached by a different branch because AEAT typed one cell in lower case.
  The branch's docstring calls the shape total-less, yet Modelo 390 does declare a total
  at row 21; it reads as total-less through that same comparison.
- The numbered pages' twelve-byte terminators do not make the closer redundant. Those
  identify a page, sit at real offsets, and are marked obligatory. Field 15 is eighteen
  bytes and closes the file. Modelo 303 emits both.
- The bundled consolidated corpus does not describe fichero structure at all, so it
  cannot arbitrate. The design workbook is the authority, and the registry already
  classifies it as layout authority with a reviewed status.
- The two hard-coded spellings are not the same kind of thing, and the whole
  implementation turns on that. `Variable` against `variable` is a comparison that was
  never meant to discriminate on case. `AAAA` against `EEEE` is a genuinely different
  token.

## Considered options

- **Add `variable` and `EEEE` to their matchers and let the red clear.** Rejected for
  `EEEE`, which is a widening, and the governing record forbids widening by matcher for
  measured reasons. It would also be uninspectable later: nothing would record which
  modelos relied on it, or why.
- **Declare the closer out of scope for auxiliary-header modelos and codify current
  behaviour.** Rejected. It reasons from the code's own consistency, and self-consistent
  code is indistinguishable from a shared mistake. Three trees agreeing with each other
  is not evidence about AEAT; the design document is.
- **Reclassify by correcting the case comparison, and admit the year placeholder by
  declaration.** Chosen. It separates the defect from the widening and applies the
  correct remedy to each.
- **Leave all three trees as they are and record the divergence.** Rejected. This is the
  under-declaration direction on emitted filing bytes, which this project's rules treat
  as never acceptable to leave silent.

## Constraints

- No mechanism widens by relaxing a matcher, a shape test or a predicate. A widening is
  an explicit declaration naming its subject and carrying its evidence.
- The design workbook is the layout authority. Nothing here may be settled by reading the
  generator, the filing path, or the published trees.
- Case folding is permitted ONLY for the design-vocabulary length and total markers,
  where the token is the same word. It is not a general licence to fold case wherever a
  comparison is inconvenient.

## Implementation

Correct the case comparison at `record_design_workbook.py:217` and `:258` so the design
vocabulary is recognised as AEAT spells it. This admits no new shape: the same token is
recognised under a different capitalisation. A regression must prove exactly that, by
asserting Modelo 390 and Modelo 232 classify as variable envelopes with their closers
intact while Modelo 303's classification is unchanged.

Admit `EEEE` as a year placeholder by declaration, not by editing the closer pattern in
place to add an alternative. The declaration names its subjects, cites the design rows,
and stays enumerable. The pattern's own comment already reasons that the year is never
asserted against a filing instance because the instance supplies it; that reasoning
covers `EEEE`, and the pattern simply predates the evidence.

Republish the affected trees through `check_generated_export_tree` and
`publish_validated_generated_export_tree`, never by hand. Both Modelo 232 revisions emit
the closer after this change, so both published trees are regenerated.

Modelo 390's 2022 tree is a special case discovered on 2026-08-31 and it changes the
sequencing. That revision is enrolled in the generated-tree gate but has never been
published, so its gate is red today with the message that the fresh render succeeds and
only publication is missing. Publishing it before this record is accepted would mint a
third published tree carrying the very omission this record exists to correct, and would
then require immediate republication. Accept or reject the closer question first, then
publish 390 once, with whatever bytes the ruling produces. The red gate is telling the
truth in the meantime and must not be silenced by publishing.

Keep `_m390_auxiliary_envelope.py` until that republication is verified. It is superseded
and byte-identical to the live pair, but it is the one module that renders page zero from
a design whose closer the live path discards, and deleting it before the fix lands
destroys evidence for the sake of tidiness.

## Rationale

The narrow-mechanism record forbids widening by matcher because a matcher wide enough for
the defect is wide enough for the false positives beside it, and because a matcher edit
leaves no record of who relied on it. Both objections apply to `EEEE`; neither applies to
case folding. Folding case does not make the predicate admit a wider class of documents,
it makes it admit the same class under the spelling AEAT used. Treating the two as one
change would either forbid a defect fix or license a widening, and both outcomes are
worse than drawing the line.

The closer question is decided on the design document because that is the only authority
which speaks to it. The alternative on offer was to infer from three trees that agree
with each other, and they agree because they share a branch, not because each was checked.

## Consequences

Three published trees change bytes. That is the cost, and it is also the point: they were
short a record terminator, and the omission stayed invisible because the code producing
it was consistent with itself.

This is not a Modelo 390 defect and must not be recorded as one. Modelo 232 shipped the
same omission from the same cause, and shipped first. A fix in the shared contract
repairs all three at once, and Modelo 390's layout swap then loses nothing at all: the
developer-identity positions return and the closer is restored for every affected modelo.

The auxiliary-envelope-header branch's justification is now in question. This record does
not retire it, because whether any real AEAT design is genuinely closer-less is a separate
question needing its own evidence. It does remove the two modelos that were its only
members, and a branch with no remaining members should be reconsidered rather than left
standing on the assumption that something must reach it.

Not established here: whether an accepted filing or a live oracle confirms the closer in
emitted bytes. The grounding is the AEAT design document, the strongest authority
available without filing and the same one every other layout decision rests on. A live
oracle that later contradicts it outranks this record.
