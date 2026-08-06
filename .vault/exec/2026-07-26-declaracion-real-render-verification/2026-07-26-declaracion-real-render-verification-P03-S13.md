---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:ff045aabe05522e336a354d08b3801f97261bfd42859c7a84cef45dbb81c98be'
step_id: 'S13'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Assess whether per-profile bilingual alternation is the right shape or merely the reachable one, and record the structural alternative

## Scope

- `.vault/exec`

## Description

Per-profile alternation is the reachable shape. It is not the right one, and the
measurement that proves it is already in hand: immunity to the render language
follows the extraction STRATEGY, not the modelo. All 124 language-immune targets
are exactly the 102 `bbox_anchored` plus the 22 `numeric_casilla` ones, and all
154 exposed targets are `named_label`. Nothing else correlates.

That is the whole finding. The language dependency is not a property of any
profile's wording; it is a property of choosing to anchor on prose at all.

## Outcome

Four reasons alternation is the wrong axis, in descending order of how much they
should weigh.

**It does not close the problem, only the observed instance.** AEAT's sede serves
the co-official languages, so a Spanish-and-English alternation would be defeated
by a Catalan or Galician render exactly as a Spanish-only pattern was defeated by
an English one. Each additional language needs its own branch on each of 154
targets, and under D3 each branch needs a render evidencing its wording, which
the repository does not have. A remedy that requires N specimens per modelo to
reach N languages is not a remedy.

**Catalan and Galician are inference, and nothing in this repository evidences
them.** No sidecar carries a language field and no bundled document mentions
either. The argument stands on how the sede is known to work rather than on
anything measured here, and it should be repeated as inference wherever the
render-language route is discussed -- including anywhere its closure is claimed.
The one thing that is measured is that the language axis is real at all, which
the English Modelo 390 render established.

**It rots silently, in the same way as the defect it patches.** An alternate
branch that stops matching produces the original failure -- a dropped box on a
render nothing tests -- and the profile still looks widened. The maintenance
surface is 154 hand-written patterns that must each stay true across every future
revision, with no gate able to check them absent a specimen per language.

**It scales badly against the actual work.** Nineteen profiles, 154 targets, and
five revisions of Modelo 100 alone account for 105 of them. Every new revision
re-authors the alternates.

**The alternative is already in the schema, and the evidence for it is one
measured point plus a structural reason to expect it generalises.** The single
target that survived on the English Modelo 390 render was its one
`bbox_anchored` target, and AEAT translates labels while leaving box numbers
alone.

That claim has been checked as hard as the corpus allows, and the honest
statement is narrower than "confirmed". The repository holds exactly **one**
cross-language empirical point: Modelo 390's box 49 is `bbox_anchored` and both a
Spanish facsimile and the English real render exist for it. Measured directly,
the anchor word sits at x0=412.81 in Spanish and x0=411.89 in English -- under a
point apart, both inside the anchor window -- so that column genuinely did not
reflow under translation. One target on one modelo is real evidence and better
than none, and it is not 102 targets confirmed.

The structural reason is what carries the rest: these strategies match on digits
and geometry rather than on prose, so there is no mechanism by which translating
a label would change what they match. That is a sound expectation, not a
measurement, and it should be read as one until more cross-language renders
exist.

The exposed half of the partition needs no such caveat. All 158 `named_label`
patterns were checked three ways -- none lacking an alphabetic run, none
acronym-shaped, none merely cognate-dependent -- with the twenty thinnest read by
hand, and an independent re-derivation reproduced the 158 / 102 / 22 census by
raw TOML parsing without the authority object model. That partition is exact.

**The structural answer is therefore to anchor on the printed box number wherever
the form prints one in a separable position**, migrating `named_label` targets to
`numeric_casilla` or `bbox_anchored`. It needs no new mechanism.

Three honest constraints on that recommendation, none of which changes it:

`bbox_anchored` trades a language dependency for a layout one. Its x-range
anchors are layout-version specific and drift when AEAT re-issues a form, which
is route R6. `numeric_casilla` does not have this problem -- it anchors on the
printed number at line start in extracted text -- so it is the better migration
target where the form's layout allows it.

`numeric_casilla` currently reads the WRONG FIELD, and would reproduce D1's
defect at scale. `_numeric_casilla_anchors` takes its anchor from
`casilla.number`, which is reviewed record-design metadata, not the printed box
number -- the identical mistake the blank-box guard made before D1. Measured: all
22 current `numeric_casilla` targets happen to carry a numeric `number`, so it
works today by the same accident that carried the guard. Pointing a
`numeric_casilla` target at a semantically-named casilla, which is precisely what
Modelo 390's and Modelo 190's totals are, would anchor on an id string or a
fichero-BOE positional range and never match. **This must be corrected to prefer
`form_number` before box-number anchoring is adopted as the migration target**,
or the migration will re-open the defect this campaign closed.

Some layouts cannot be reached by either. Modelo 100 prints the box number in a
smaller font overlapping the amount's own x-range, so all three `bbox_anchored`
value offsets fail on it numerically, and `numeric_casilla` anchors at line start
while that number sits at line end. Those profiles need the estate-wide
capture-contract change already scoped separately, and no amount of strategy
migration reaches them first.

## Notes

The recommendation is recorded, not built, as the Step asks. Building it is a
larger decision than this campaign should take: it changes the extraction
strategy of up to 154 targets, it depends on the `form_number` correction above
landing first, and for each target it needs the printed box number to be known --
which is the same evidence problem that left three Modelo 193 guards blocked.

What can be said without further work is that the migration is not uniform. It is
cheap where the form prints a separable number and the registry already records
it, and impossible where the layout merges the number into the value. A first cut
would be to measure, per exposed target, whether a printed box number is both
known and separable, which is decidable from the registry plus one render per
layout family.

One scoping caution. This assessment is about which field the extraction anchors
on, and it should not be read as an argument to delete `named_label`. That
strategy is correct where the form prints no box number at all, which is the case
for several informativa summary lines, and the campaign has no evidence that any
particular target can be migrated -- only that the axis is wrong in general.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on; the strategy counts and the `numeric_casilla` anchor-field measurement both
come from loading every revision through the registry authority.
