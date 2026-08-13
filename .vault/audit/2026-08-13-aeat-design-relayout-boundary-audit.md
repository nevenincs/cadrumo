---
tags:
  - '#audit'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f9f2b88eeeade833691178afe1e0710e4c4214c0f9e83b947f85932204335202'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-sub-year-epoch-adr]]"
---

# `aeat-design-relayout-boundary` audit: `Campaign closure: overtaken rulings, the grounding gap, and the blocked state`

## Scope

This campaign's closing phase requires five closing findings and one honest
statement of the campaign's live blocking condition. Each finding below was
re-verified against HEAD at the time this document was written rather than
copied from the row text that requested it; where a row's own figures were
re-derivable independently they are re-confirmed, and where a claim rested on
a live probe the probe was re-run and its output is quoted verbatim.

## Findings

### modelo-200-no-implementation-ruling-overtaken | high | the first accepted record's no-action ruling for Modelo 200 no longer holds and must not be read as in force

The first accepted decision record ruled no implementation action for Modelo
200 on the ground that its two-design span is offset-identical. That ruling
is decisively overtaken. The hardened span gate reds on Modelo 200 with a
RECORD SET CHANGED signal of 75 records against 77, and once the gate's
box-number marker was widened to the five digits Modelo 200 actually uses, an
offset shift of 1140 of 3194 shared boxes plus 246 boxes added and 145
removed. The offset-identity claim is refuted on its own terms rather than
merely superseded by new evidence: under the previous four-digit marker the
gate keyed only 23 of that modelo's boxes and could not see the relocation at
all, so the record's own instrument was measuring the wrong slice of the
modelo when it reached its verdict. A later reader must not treat the first
record as still in force on Modelo 200's no-action posture; the campaign's
`W04` Wave acted on Modelo 200 precisely because this finding overtook it.

### modelo-303-epoch-count-and-prescripcion-grounding-gap | high | the sub-year record's revision-pair finding was overtaken by occupancy measurement, and the four-year window rests on an ungrounded pair of Ley articles

Two distinct items, recorded together because both surfaced from the same
Modelo 303 measurement pass. First, the sub-year decision record's finding of
one layout-identical Modelo 303 revision pair was overtaken by an occupancy
measurement: the open-ended revision this campaign inherited spans **five**
design epochs, not the four the sub-year record described, because the 2023
and early-2024 designs are themselves not layout-identical — four Regimen
Simplificado employee-count slots are real in the 2023 design and reserved in
the early-2024 one at unchanged sheet offsets. No pair among the five may
share a copied export fragment tree; each of the five epochs needs its own
parsed tree.

Second, and separately: the four-year prescripcion period bounding this
campaign's authoring scope is grounded on this tree's own canonical
retention-floor constant, not on bundled corpus text. Ley 58/2003 articles 66
and 67 — the BOE articles that actually establish the four-year prescripcion
period in law — are **not** bundled in the corpus tree; confirmed by absence
in `src/cadrumo/_data/corpus/normatives/html/`, which carries other Ley
58/2003 articles (5, 26, 27, 119, 120, 122, 213) but neither 66 nor 67. What
IS bundled is the per-period voluntary deadline the window is measured
*from*: Orden EHA/3786/2008 article 7 for Modelo 303 and Orden EHA/3111/2009
article 8 for Modelo 390, both confirmed present in the same corpus
directory. This is an open honesty item, not a closed one: the campaign's
scope boundary is correct in that it matches the legally-established period,
but the corpus does not yet carry the text that establishes that period, only
the text the period is counted from.

### modelo-200-ejercicio-gap-2022-2023 | medium | ejercicio 2022 and 2023 sit inside the prescripcion window with no claiming revision and refuse as a coverage gap, deliberately left open

Modelo 200 ejercicios 2022 and 2023 sit inside the prescripcion-reachable
window while no registry revision claims them: at HEAD the modelo carries
exactly one revision directory, `2024-y-siguientes`, whose `period_selector`
starts at `year_from = 2024`. Ejercicios 2022 and 2023 therefore refuse
today, and the refusal is a **coverage gap** — no revision candidate at all —
rather than a mis-write at wrong offsets, which is the defect class this
campaign exists to close. Re-run against HEAD through the production
selection path (`ValidatedRegistryAuthority.snapshot`, bundled registry,
Modelo 200, period `0A`):

    ejercicio 2022: REFUSED -- modelo 200: no revision for year=2022 period='0A' revision=None
    ejercicio 2023: REFUSED -- modelo 200: no revision for year=2023 period='0A' revision=None

This campaign deliberately does not close that gap. The standing goal is that
no filing year is written at wrong offsets, not that every reachable year is
served; authoring a Modelo 200 revision for ejercicios 2022–2023 is new
registry-authoring work outside what this campaign's Waves scope, and doing
it here would silently widen the campaign rather than close it.

### modelo-720-one-year-underhang-outside-scope | low | a one-year underhang between the 720 revision's claimed ejercicio and its design's applies_from is reported, not actioned, because scope governs what changes, not what is reported

Outside this campaign's scope, reported for the same reason the Modelo 123
finding was. Modelo 720's only revision, `2013-y-siguientes`, declares
`period_selector = { year_from = 2012, periods = ["0A"] }` — it claims
ejercicio 2012. Its only declared layout design, the bundled AEAT record
design catalogued as `sources."aeat-dr-720"`, carries `applies_from =
2013-02-01`. The underhang reproduces exactly as described: a design whose
own catalogue entry declares it applicable from 2013 is being used to cover
an ejercicio the revision itself dates to 2012, a one-year underhang rather
than the multi-year drift this campaign was built to find and close. Either
the period selector reaches a year before AEAT published a record design for
this modelo, or the source catalogue's `applies_from` is a year conservative
relative to when the design actually became usable for ejercicio 2012
filings; distinguishing those needs someone who knows Modelo 720's first
filing year under this design, which is outside what this campaign's
measurement instruments can settle. The principle this rests on: scope
governs what is changed, not what is reported, so this is recorded here and
left for the Modelo 720 owner rather than actioned inside this campaign.

### ambiguous-revision-refusal-sentence-year-naming-deferred | low | whether the ambiguous-revision refusal should name the filing year in its localised sentence is deferred deliberately, not overlooked

The ambiguous-revision-selection refusal's localised sentence does not name
the filing year explicitly in its own text. Deciding whether it should was
considered and deferred rather than overlooked. The year already reaches the
operator through the refusal's structured context and through the
raiser-supplied suggestion that accompanies it, so the omission costs clarity
rather than actionability — the operator is never left without the year, only
without it restated inside the sentence itself. Changing the sentence means
touching all four locale catalogues (`en`, `es`, `ca`, `hu`), which at the
time of this campaign's closing phase carry several other agents' uncommitted
translation work in the same files. The trade was judged not worth making for
information the operator already has by another channel, against the cost of
opening four contended locale files for a wording-only change.

## Current blocked state

A reader arriving at this document after the fact needs the campaign's actual
standing, not only its five closing findings, because three of its four
authoring Waves are not merely incomplete but structurally blocked on a
sibling campaign. Each fact below was verified against HEAD before being
recorded here.

Every export fragment tree for Modelo 303, Modelo 200 and Modelo 390 is
deleted at HEAD: `git ls-files` over each modelo's `revisions/*/export/*`
returns zero files for all three. The deletion was performed by the sibling
campaign `2026-08-10-aeat-export-fragment-generator-authority-plan`, not by
this one.

Modelo 303 now carries six revision directories at HEAD —
`2009-y-siguientes`, `2023`, `2024-desde-09-y-3t`, `2024-hasta-08-y-2t`,
`2025` and `2026-y-siguientes` — five of which are the split shells this
plan's `W02.P04` authoring rows describe. Those five directories carry full
registry sections (bindings, casillas, constructs, formulas and the rest) but
an empty `export/` directory each, and were landed by commits belonging to
the sibling export-fragment-generator campaign rather than by this plan's own
authoring rows.

No semantic map exists for any modelo, and `dev/registry/mappings/` does not
exist at HEAD. A semantic map is the reviewed meaning-only artefact the
generator authority governing this work requires before a parsed, non-hand-
transcribed export fragment tree can be authored at all.

Consequently this plan's Waves `W02`, `W03` and `W04` — every authoring row
that would populate an export fragment tree for Modelo 303, Modelo 390 or
Modelo 200 — are blocked on that sibling campaign landing the generator and
at least one reviewed semantic map. The governing
`2026-08-10-aeat-export-fragment-generator-authority` decision record
forbids hand-transcription as the workaround: an export tree must be parsed
from the bundled diseño de registro through the generator, never
hand-authored to unblock this campaign sooner.

**Scope-narrowing note, per campaign-close discipline.** This campaign's
standing goal is that no filing year is written at wrong offsets for Modelo
303, Modelo 390 and Modelo 200 across the reachable prescripcion window. What
that goal still asks for, and what this blocked state excludes for as long as
it persists: a correctly re-laid-out, exportable revision for every in-window
filing year on all three modelos. Today only the pre-split registry sections
(bindings, casillas, constructs, formulas, verification expectations) exist
for the split shells; none of them can produce a correct export until the
sibling campaign's generator and semantic maps land, so the standing goal is
not met for any filing year that depends on a post-split Modelo 303 or Modelo
390 revision, or on the Modelo 200 revision this plan's `W04` Wave
re-scoped. This campaign does not narrow that goal — it records the
dependency and waits on it, per the plan's own ordering rule that `W02`,
`W03` and `W04` may proceed once `W01` lands, which does not anticipate a
cross-campaign block on the fragment tree itself.

## Recommendations

- Do not certify any Modelo 200 authoring row against the first accepted
  record's original no-action language; the record stands corrected by this
  audit's first finding and by the campaign's own `W04` Wave.
- A follow-on ADR amendment should rule on whether Ley 58/2003 articles 66
  and 67 are added to the bundled corpus tree so the four-year prescripcion
  window is grounded on the establishing law rather than on the
  retention-floor constant alone.
- The Modelo 200 ejercicio 2022–2023 coverage gap and the Modelo 720
  one-year underhang are both out of this campaign's authoring scope; each
  needs its own future plan row rather than an in-campaign fix.
- Track the sibling `2026-08-10-aeat-export-fragment-generator-authority-plan`
  as a hard precondition for resuming `W02`, `W03` and `W04`; do not attempt
  a hand-transcribed export tree to unblock sooner, per the governing
  decision record.
