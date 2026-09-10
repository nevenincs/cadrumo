---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2bf694412c172c3fae20ee7e135aeed95a706fafb1f06fecfc43c0ef72ea9652'
step_id: 'S47'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [L | opus-medium] DONE. All four modelos adjudicated one at a time, and each did fail differently. The label-derived one fell from 620 unchainable to 134 once the key was corrected and orphaned 21 rows. The reassignment one is CONFIRMED and larger than suspected — both the identifier and the concept behind the printed number moved, six boxes were inserted and the displaced concepts reappear six lower — giving 233 genuinely new rows, 124 recoverable, zero refusals, 115 held for one human pass and 1 withheld on a type flip. The wholly-new-edition one reproduces its 383 exactly and is NOT inflated, but only 110 rows are boxes AEAT added, zero are renumberings, and 248 were printed on the official form all along while the corpus's own thin extraction epoch never declared them. The shared-role one restates at 276: 243 genuinely new numbers proven absent from the predecessor design, and 33 that are a predecessor DECLARATION GAP rather than new boxes. Three things came out of it that outlive the four: the sha-pinned official record design is the strongest oracle where bundled and proves retirements as well as additions; a byte span alone must never chain; and a printed box number is unique per pagina, not per modelo. Proof met: every unchainable row per modelo is chained with evidence or declared new, and the two rows with no legal authority found are recorded as such rather than inferred.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Changes

- `M` `.vault/adr/2026-09-09-registry-edition-authoring-adr.md`
- `M` `.vault/plan/2026-09-09-registry-edition-authoring-plan.md`

## Notes

Adjudication only; no registry data changed. Four rulings held in session scratch, one per modelo,
each carried into the ADR and into the S06 and S19 Step rows. Two rows of the corpus have no legal
authority anywhere in this repository and are recorded as ungrounded rather than inferred. One live
defect was found outside this campaign's surface and reported to the owning lane: 33 wire slots in
one modelo's shipped layout are bound to the wrong-page casilla, because its printed box number is
unique per pagina rather than per modelo.
