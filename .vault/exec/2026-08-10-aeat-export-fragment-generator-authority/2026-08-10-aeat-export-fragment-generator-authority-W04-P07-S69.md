---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:8cd718d06fa20a58979e7f6c6032997e21e3b811d3f25da21cc0e7cac3fb5f7f'
step_id: 'S69'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Author and review the Modelo 303 2024-late-epoch semantic map and source-bound render profile, exact-bijecting all 413 fixed-record anchors plus the 13 DP30300 prefix anchors, 426 in total, each to its one canonical typed authority. This epoch adds 20 fixed anchors over 2024-early, so review every added anchor and every delta that moves a semantic home rather than an offset by hand. Of these anchors 140 are nonnumbered DP30302 simplified-regime anchors whose projection endpoint declarations S63 supplies, so this row cannot close before S63 lands and its DP30302 share must be re-counted against the post-S63 declaration index. Do not inherit the 2023 or 2024-early amendment-evidence assignment: from 2024-late onward DP30303 ordinal 29 declares a rectificativa self-assessment with additional rectification-motive fields, which moves the semantic home between the complementaria and rectificativa amendment-evidence producers rather than shifting an offset, so that region is hand-reviewed per epoch

## Scope

- `dev/registry/mappings/modelo_303/2024-late/`
- `dev/registry/render_profiles/modelo_303/2024-late/`

## Status

Authored, not closed. The row stays unchecked: mandatory code review has not
run, and the owning coordinator is not closing rows in this chain until the
suite verdict is attributed. The work below is complete and measured; the
closure decision is deliberately withheld rather than pending.

## Description

- Consolidate the two per-design Modelo 303 census modules and their two test
  modules into one epoch-discovering census and one suite, and add the
  2024-late mapping set of seven fragments.
- Verify the 2024-late bijection against the real parsed design rather than
  against the reviewed expectation table.
- Enumerate by measurement every anchor the 2024-late layout adds over
  2024-early, and every anchor whose semantic home changes rather than shifts.
- Add a per-epoch introduced-and-retired semantic-home review, compared by
  fully-qualified home identity against the predecessor epoch's real map.
- Add a predecessor-chain check so a newly authored epoch cannot satisfy that
  review vacuously by declaring itself the root.
- Prove the new review bites, from outside the repository, against two
  mutations the existing census cannot see.
- Refuse explicitly, rather than dereference `None`, when official content
  matches a trailing note reference carrying no note number.

## Outcome

The 2024-late epoch exact-bijects 426 anchors: 413 fixed-record anchors plus
the 13 DP30300 prefix anchors. The map carries 413 entries and the mapping is
one-to-one in both directions, with no duplicate anchor on either side and no
unmapped or extraneous anchor. Per record the fixed anchors are DP30301 88,
DP30302 163, DP30303 38, DP30304 43, DP30305 68 and DP303DID 13. The
nonnumbered DP30302 simplified-regime share measures 140, being the two
declaration-index spans of 144 ordinals less the four the design reserves as
fillers, which matches the contracted share re-counted against the post-S63
index. Map and render profile both declare the 2024-late design source and its
digest, and the census asserts that digest against the parsed design's own,
so the chain from map to source catalogue to bundled file closes without a
transcribed copy of either value.

The layout grows by 20 anchors while the semantic content grows by 22
introduced homes and one retired home, because the DP30303 re-layout reclaims
reserved filler space instead of only appending. In DP30301 six anchors carry
the transitional super-reducido rung and its recargo de equivalencia
companion, resolving to casillas 165 through 170; the tipo slot states the
constant two per cent and the recargo tipo admits the two published rates. In
DP30302 ten anchors carry simplified-regime facts: an eligibility flag
inserted mid-record for each non-agricultural slot, and eight appended
amounts covering the agricultural eligibility flags and reduction amounts, the
non-agricultural reduction amounts, and the Lorca reduction amounts the same
re-layout gave their own slots. In DP30303 four added anchors carry six
introduced homes: the prior-domiciliation action, two resultado casillas, and
the two itemised rectification motives.

The amendment-evidence region was hand-reviewed for this epoch rather than
inherited, as the row requires. DP30303 ordinal 29 stops being the
complementaria marker and becomes the rectificativa flag, which retires one
computed home and introduces one producer home rather than shifting an offset.

The introduced-and-retired home review closes a gap the census cannot reach.
The census counts homes by class, so exchanging two casillas, or exchanging
two simplified-regime cohorts, leaves every class total identical while
sending a taxpayer figure to a different official box. The review compares
fully-qualified home identities, including projection cohort, fact and slot,
so a pure offset shift stays silent while an authority change fails closed.
Both mutations were applied to a real loaded map in memory, with no tracked
file altered: the census stayed green on both and the review refused both,
naming the relocated homes and their measured anchors.

That review reaches exactly the homes an epoch introduces or retires, which is
narrower than the sentence above reads on its own. It compares set membership,
so exchanging two homes the epoch INHERITS changes neither set and passes. A
later epoch's work measured that blind spot directly and closed it with a
second gate: two epochs' anchors are corresponded by what their designs
themselves declare, and every corresponded anchor must carry the same home in
both. The two gates are complementary rather than redundant -- the first covers
what changed at the boundary, the second covers what did not.

Verification ran sequentially with full output written to a log and read back.
The owned suite reports 82 passed, no failures and no errors, up from 78
before the review was added, and was re-run green after the concurrent
review-status repairs landed in the shared fixtures. Lint, format and type
checks pass on the owned surface.

## Notes

The working tree amends closed work, and that is recorded here because a
closed row that quietly changed is the drift this chain exists to stop. The
consolidation re-homes DP30301 ordinal 32 from a hard literal to casilla 154
in BOTH the 2023 and the 2024-early epochs. Those epochs belong to rows S67
and S68, which are already closed and whose audits recorded zero findings
against the pre-amendment state. The change moves each epoch's casilla total
from 105 to 106 and its literal total from 40 to 39. It is visible only in the
working-tree diff otherwise.

The amendment is grounded rather than incidental: the bundled design labels
that slot as the tipo for casilla 154, and from 2024-late the slot states no
constant at all, so the casilla home is the only home available there. The
open question is consistency, not this slot. Six structurally identical slots
in the same record carry the same note-seven marker and remain hard literals
in every mapped epoch, so one epoch now homes the same source shape two ways
with no declared discriminator. That was escalated and is being opened as its
own row with its own decision record, because it is a semantic-home ruling
with filing-grounding consequences across three epochs and two closed rows,
and the deciding input is a tax review against official text rather than a
code judgement. No home was changed and no discriminator was added here.

Two failures in a peer-owned module that consumes the shared export-tree
surface are not attributable to this work: one is the modelo 200 pending
review refusal being repaired elsewhere in the chain, and the other is a
duplicate administrative fragment prefix raised by the registry loader cache
on a modelo 200 oversized-record partition. Both originate in peer-modified
registry package code and neither can be reached from a Modelo 303 content
grammar change.

No published revision tree was touched, no review status was promoted, and the
superseded per-design census and test modules stay deleted with no bridge,
alias or fallback.
