---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S02'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Verify M111 against its four real specimens, 29 bbox targets under a vacuous zero floor, covering routes R3 and R6

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/111`
- `declaracion tests`

## Description

Modelo 111 is the one profile in this phase with several real specimens, so it is
the only one where a coverage floor could be argued from evidence rather than
guessed from a single document. The four quarters of 2024 were measured through
the production extraction path against the live profile, which declares 29
`bbox_anchored` targets, `min_coverage = "0"` and `failure_semantics = "fail_hard"`.

Measured coverage: 1T, 2T and 3T each score 5 of 29 (0.1724); 4T scores 1 of 29
(0.0345). No target came back malformed or ambiguous on any quarter.

The absences were checked against the printed documents rather than assumed. The
1T render prints `Rendimientos dinerarios ... 01 02 03` and `... 04 05 06` with
nothing following the box numbers, and prints `07 1 08 1.000,00 09 1.000,00` on
the actividades economicas row. This filer declared only rendimientos de
actividades economicas, so twenty-four boxes are legitimately blank and the
profile is reading the document correctly. The fourth quarter is sparser still:
its printed `28` and `07 08 09` carry nothing and only box 30 is populated.

That reading is independently corroborated by the specimens' own redaction
manifests, which are authored by the sanitiser and not by any profile: 1T, 2T and
3T each declare six amount replacements, 4T declares one. The manifest count
matches the populated-box count on every quarter, so the sparse 4T is a genuinely
sparse filing rather than a specimen the parser failed to read.

Route R6 is exercised well here and passes: 29 x-range bbox anchors resolve
correctly across four independently rendered documents, and no anchor drifted.

## Outcome

Route R3 resolves against the evidence, and it resolves against raising the
floor. Four real specimens agree that a valid Modelo 111 filing can populate as
little as one of the profile's twenty-nine targets. Any floor above 1/29 would
refuse the real 2024-4T filing outright under `fail_hard`. The floor therefore
stays at zero and was not changed.

This is a stronger statement than the Modelo 390 case, where a single specimen
made any floor under-evidenced. Here the four specimens positively establish that
no useful floor exists for this profile, so the vacuous zero is not a gap waiting
on more evidence but the correct setting given how the form is used. The
extracted-set assertion is what does the policing.

The four quarters are folded into the shared real-render gate for the coverage
floor and the provenance premise, which the existing per-modelo boundary test
does not express. That boundary test already drives all four end to end through
`parse_declaracion` and asserts exact values including the 4T exclusive-set
assertion, so the new gate deliberately does not restate those value claims.

Verification: the full declaracion suite passes (`227 passed`), which includes
both the pre-existing boundary tests and the four new specimen rows.

## Notes

No profile change was made for Modelo 111 and none is warranted. The profile
reads all four real renders correctly.

The blank-box guard could not be exercised on this profile and is not claimed to
have been: all 29 targets are `bbox_anchored`, and the guard is scoped to
`named_label` targets, which capture the last token on a line. Every one of these
29 targets does map to a genuine printed box number, so were any converted to
`named_label` the guard would arm correctly, unlike Modelo 390 and Modelo 190.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy with an empty
degraded-reasons list. No semantic result was relied on.
