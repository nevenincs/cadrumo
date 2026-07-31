---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:73d795c7b9129f51da6001608aae99fcfa70322d69a2b873d79ef14ec16fae80'
step_id: 'S20'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Wire D4 so it stays true, by having the real-render gate import the production profile selector rather than hand-copying its logic

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests`

## Description

- Read the gate's own selection helper and confirm it re-implemented the
  production filter rather than calling it.
- Replace the hand-copied comprehension and its local assertion with a call to
  `_select_extraction_profile`, the function the parser itself uses.
- Rewrite the helper docstring, which had stated the duplication as an
  intention, to record why calling is the point.
- Run the gate and the whole adapter suite to confirm every specimen still
  resolves through production selection.

## Outcome

Landed in commit `973c9084fd`.

The gate exists to prove a `declaracion_pdf` profile can read a real AEAT
render. That claim holds only for the profile the parser would actually choose,
and the gate was re-deriving the choice: it filtered
`revision.extraction_profiles` on `surface == "declaracion_pdf"` and
`"declaration_pdf" in accepted_artefact_kinds`, byte-identical to the production
selector, then asserted exactly one match.

Its docstring said so outright -- "Select the profile exactly as
`_select_extraction_profile` does" -- so the divergence risk was stated as an
intention rather than noticed as a defect. A copy cannot stay exact. Had
production's notion of a declaracion_pdf profile moved, the gate would have kept
certifying a profile the parser no longer selects, with every assertion still
green over the wrong subject. That failure mode is worse than a red gate,
because nothing would report it.

The re-implementation was also a trap the original author had already fallen
into once and documented in the same docstring: selecting on `artefact_kind`
rather than `surface` returns nothing for half the tree, because that field is a
free-form `str` the registry splits between `"declaracion"` and
`"declaration_pdf"`, and the miss reads as "this modelo has no declaration
profile" rather than as an error. Calling the selector removes the opportunity
to get that wrong a second time.

Zero-profile and multi-profile modelos now raise `DeclaracionParseError` from the
selector rather than a local assertion, which is the refusal an operator meets on
the same condition.

Verification: 45 gate cases and 236 declaracion adapter tests pass, so every
specimen resolves through production selection unchanged -- which also shows the
two selection sets agreed in practice for as long as the copy existed. Collection
clean at 14,773; ruff clean.

## Notes

Executed by an adjacent campaign working the reconcile and evidence surfaces,
which reached this step after its own plans closed. The step's file scope was
verified to carry no uncommitted work before any edit.

Semantic search was unusable throughout: the code index held roughly 68 sections
against roughly 4,546 source files while reporting itself healthy, so the
duplication was found by reading the production selector and the gate side by
side rather than by a similarity query.

Steps `P03.S11` through `P03.S14` were deliberately left untouched. Their exec
records exist as empty scaffolds, untracked, which is the signature of an agent
interrupted at a session limit -- the same signature commit `429efb0988` records
for two earlier records in this campaign. Writing them would duplicate work their
owner will resume.
