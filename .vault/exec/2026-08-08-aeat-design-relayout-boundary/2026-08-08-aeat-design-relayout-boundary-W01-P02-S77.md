---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5f515925e79b5c623582c104eaa23063a86fea4cb445f1684a4e6421d1d3029b'
step_id: 'S77'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-09-aeat-design-relayout-boundary-modelo-200-fragment-tree-provenance-research]]"
  - "[[2026-08-13-aeat-design-relayout-boundary-audit]]"
---

# HELD: both ruled mechanisms are measured-blocked and neither may be re-proposed without new evidence

## Scope

- `dev/registry/`

## Description

- Attempted the two mechanisms the row rules on for pairing Modelo 200's
  export fragment tree against the published record design: full generation
  from the design, and re-coordination of the existing tree against it.
- Measured the pairing rate of the existing tree's fields against the
  design's own slot numbering, and classified every unmatched field by the
  reason it failed to pair.
- Re-verified the measurement's standing against HEAD before closing, since
  the population it counted has since been deleted from the tree.

## Outcome

**Negative result, and it is the answer rather than an obstacle.** Both ruled
mechanisms are measured-blocked and neither may be re-proposed without new
evidence.

Full generation from the design is blocked on the same casilla-to-box mapping
the span gate exists precisely so it need not depend on. Adopting it would
reintroduce the dependency the gate was built to avoid.

Re-coordination is blocked on its own measurement. Of the existing tree's
6,537 fields, only 2,402 paired unambiguously against the design the tree
already declares — 36.7 percent. The remainder decomposes rather than
scattering: 42.3 percent of casilla ids match SEVERAL slots, because AEAT
repeats one box across regimen segments and prorrata rows so a box number is
not a unique key within a single design; 18.9 percent are literal and draft
envelope fields the design never numbers at all; and 2.1 percent match no
slot. Refuse-on-ambiguity therefore refuses on 63.3 percent of the tree, and
the only way to break the 42.3 percent tie is to disambiguate by position —
which is the index-keyed pairing the sub-year decision record already
retracted. Re-coordination has no admissible key left.

**That rate is EXPLAINED rather than anomalous, and the distinction is the
whole ruling.** The tree was never derived from a design in the first place,
so there is no reason its 6,537 fields should pair with the design's 6,808
slots. A better key cannot rescue the pairing, because the failure is not one
of key quality — there may simply be no mapping to find. Nobody should
re-attempt this expecting a smarter key to raise the rate.

## Notes

Two facts have moved since the row was written, and the record is honest
about both.

**The measured population no longer exists in the tree.** Every Modelo 200
export fragment was deleted at HEAD; `git ls-files` over the modelo's
`revisions/*/export/*` returns zero files, the deletion carried by the commit
subject `Registry work: 200` of 2026-08-11. The 6,537 fields this row
measures are therefore a historical population, and the percentages above
describe a tree that is no longer present. The ruling survives the deletion
intact — indeed it is strengthened, since any future tree must be parsed
through the sibling generator authority rather than paired against the
deleted one — but the figures must not be re-run against HEAD expecting to
reproduce, because there is nothing left to count.

**The provenance investigation independently corroborates the conclusion from
the authoring side.** That investigation found the tree was hand transcribed
from the AEAT Diseno de Registros workbook with no parsing tool in existence
at the time, which is exactly why no mapping to the design's slot numbering
should be expected to exist: a transcriber working from the workbook's visual
layout never recorded the slot indices that a pairing would have to recover,
so the low match rate is the signature of an independently authored artefact
rather than of a degraded mapping. The two instruments agree on the field
count exactly, confirming both counted the same population.
