---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S03'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Verify M100 across its five revisions against three real specimens, covering routes R4 over-strict floor and R10 multi-revision blind spot

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100`
- `declaracion tests`

## Description

This Step is OPEN. What follows is the handover a future author needs, not a
record of completion.

Route R4 does not reproduce and route R10 is only half-decidable. The measured
defect is neither: Modelo 100 scores coverage 1.0000, 21 of 21, on all three real
specimens, satisfying its floor of 1, while **not one extracted value is the
amount printed on the page**.

The mechanism, at glyph level on `2021-0A` page 4, casilla `0545`. Twelve
size-9.00 glyphs at top 144.80 spell the printed amount `1.001.000,00`, running
x 513.97 to 566.51 with each glyph's x1 equal to the next one's x0. Four size-6.00
glyphs at top 147.20 spell the printed box number `0545`, running x 552.66 to
566.00 -- inside the amount's own span. Merging by x-position yields the single
token `1.001.0000,50405`, which parses as a valid `Decimal` and is counted
covered. Every one of the 21 targets on each of the three specimens has this
shape.

Attribution of the amount itself: the specimens print exactly two amount forms
document-wide and nothing else, `1.001.000,00` and `1.000,00`, in counts 54/16,
58/15 and 58/19. Twelve characters and eight. The sanitiser is length-preserving:
it wrote the declared `1.000,00` into eight-character fields and a
twelve-character variant into twelve-character ones, recording only the former in
the manifest. So `1.001.000,00` is genuinely printed, no second same-size merge
remains, and no real taxpayer data is exposed -- 54 unrelated boxes carrying one
identical value cannot be real.

## Outcome

Modelo 100 is excluded from the real-render gate rather than enrolled with
weakened assertions, and the exclusion is now asserted rather than described.
Enrolling it would have pinned a fabricated value as expected behaviour, which is
the pathology the gate exists to end.

Scope correction absorbed: three revisions have specimens, not five. `2021-0A`,
`2022-0A` and `2023-0A` resolve to revisions 2021, 2022 and 2023. Revisions 2024
and 2025 have no specimen and are recorded as evidence gaps under D3; a
2021-2023 measurement is not allowed to stand for them, which is the R10 blind
spot this Step exists to close.

Two things did land under this Step's scope. The blank-box guard hazard on the
Modelo 100 targets does not apply -- all 21 map to a genuine printed box number
-- and the profile `legal_refs` omissions on revisions 2024 and 2025 were closed
against the union of their targets' own refs, 16 and 17 respectively against 14
carried.

## Notes

Handover facts for the follow-on campaign, which is scoped elsewhere.

**Where the merge is.** These targets are `named_label`, which reads page text,
not the word path. A change to word assembly does not touch them. The text comes
from the pdfplumber primitive shared with the other inbound PDF adapters, because
the pypdfium2 fast path declines these files -- its canary does not match, so
extraction falls through. Any repair therefore starts in a shared module whose
other consumers have not been measured.

**No bbox anchor can express the layout.** Measured on `2021-0A` casilla `0545`,
amount x0 513.97 x1 566.51 top 144.80 bottom 153.80, box number x0 552.66 x1
566.00 top 147.20 bottom 153.20. `right_of_number` needs amount.x0 greater than
box.x1: 513.97 against 566.00, false. `left_of_number` needs amount.x1 less than
box.x0: 566.51 against 552.66, false. `above_number` needs amount.bottom less
than box.top: 153.80 against 147.20, false. Re-pointing the profile at
`bbox_anchored` is unavailable without a new anchor mode, which is a schema
change.

**Per-modelo delta of a size-aware text path**, measured over every profile with
a fixture, 21 specimens across 18 profiles. Only Modelo 100 changes; every other
modelo is byte-identical. Modelo 100 goes 21 of 21 to **0 of 21** against a floor
of 1, so it would refuse every real render. The reason is that with the tokens
correctly separated the line reads `... 1.001.000,00 0545`, and `named_label`
captures the last token, so the blank-box guard correctly reports the target
missing. Separating the fonts is necessary and not sufficient.

**Prototype of the second half.** Generalising the existing guard -- if the last
token is the target's own printed box number and a well-formed amount precedes
it, that amount is the value -- recovers 19 of 21 on all three specimens, with
distinct extracted values `1000.00` and `1001000.00` and zero fabrications. The
two stragglers are `0595` and `0670`, which the prototype's crude line regex
matched twice; the production pattern differs and they may resolve. Note that 19
of 21 still falls below the floor of 1, so a floor decision under D2 is entangled
with the fix and cannot be taken from three specimens of one filer.

**Why this was not done here.** Three coupled decisions, not a bug fix: touching a
shared inbound-PDF primitive whose consumers are unmeasured, changing what "the
value on this line" means for every `named_label` target in the estate, and
setting a Modelo 100 floor. The coordinator is scoping it as its own record.

**Manifest fidelity is a corpus defect in its own right.** The sidecar declares
one replacement constant while the sanitiser rendered two. Every value claim any
test makes against a `real_corpus` specimen inherits this, and it is why the
real-render gate's manifest check cannot police Modelo 100 even after a repair:
18 of the 19 recoverable targets print a form the manifest never mentions.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy with an empty
degraded-reasons list. No semantic result was relied on. Every number here comes
from glyph-level inspection of the rendered PDFs, from loading revisions through
the registry authority, or from running the production extraction path.
