---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:f6b1dde8d4a5f50e518aa7013931f371a5dafb0b61ad9d64e8be0a03b9934c01'
step_id: 'S10'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Measure route R12 language exposure across all 29 declaracion_pdf profiles, separating targets that depend on Spanish prose from those anchored on box numbers or numerals

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`

## Description

AEAT serves the sede justificante in the language the filer chose, and translates
the printed labels with it. A `named_label` target anchored on Spanish prose is
therefore a dependency on the filer's language setting, and nothing in the suite
would show it: the generated corpus is Spanish, and so is every bundled render
but one.

The exposure is decidable statically, without any specimen, so it was measured
across all 29 profiles by loading each revision through the registry authority
and classifying every target. A target is language-immune when its strategy is
`bbox_anchored` or `numeric_casilla`, which anchor on the printed box number, or
when its `label_pattern` carries no alphabetic run of three or more characters.
Otherwise it depends on prose.

Profiles were keyed by revision and profile id together. Keying by profile id
alone collapses Modelo 303's two revisions, which share the id
`modelo-303-declaracion-pdf`, and silently drops the twelve-target 2023 revision
in favour of the four-target 2009 one.

## Outcome

29 profiles, 282 targets: 154 depend on Spanish prose, 4 carry a second language,
124 are language-immune.

By strategy: 158 `named_label`, 102 `bbox_anchored`, 22 `numeric_casilla`. The
124 immune targets are exactly the latter two groups, which is the finding in one
line -- immunity follows the strategy, not the modelo.

**19 of the 29 profiles would extract nothing at all from a render in another
language.** Every one of their targets depends on Spanish prose: Modelo 100 on
all five revisions at 21 targets each, Modelo 303 on both revisions at 12 and 4,
Modelo 349 at 4, Modelo 180, 190, 193, 232 twice and 369 at 3 or 2 each, and
Modelo 036, 115, 184, 347, 720 and 840 at 5 or fewer. Modelo 390 is the only
partially-widened profile, at 1 Spanish-only of 10.

The remaining 8 profiles are wholly immune and would be unaffected: Modelo 111 at
29 targets, Modelo 130 at 19, Modelo 131 on three revisions at 15 each, Modelo
123 on two at 14 and 8, and Modelo 202 at 4.

Modelo 303 is the worked example and it is the profile this campaign certified
first. Its twelve targets on `2023-y-siguientes` are all Spanish-only prose, so
the profile validated against four Spanish facsimiles would read nothing from an
English render of the same form. Nothing about that is a Modelo 390 defect.

## Notes

One correction to the measurement, found by reading rather than by the
classifier. An automatic detector counted a pattern as carrying a second language
when it contained an alternation whose branches both held prose. That is
structurally right and semantically wrong: Modelo 115's casilla `04` alternates
`(?:declaraciones|autoliquidaciones)`, two Spanish synonyms. Every prose
alternation in the estate was therefore enumerated and read. There are five, and
four are the Modelo 390 patterns widened earlier in this campaign. Modelo 115 is
5 of 5 Spanish-only, not 4 of 5, and the totals above carry the correction.

The detector cannot distinguish a language from a synonym without a language
signal, and no such signal exists in the registry. The enumeration is small
enough to read, so this was resolved by reading it; a future sweep should not
trust the structural test on its own.

Modelo 036 needed a period from its own `period_selector` -- `alta`, not a
quarter or `0A` -- and returned no snapshot until that was used. An absent
snapshot reads as "no profile" rather than as an error, which is the same shape
as the `artefact_kind` trap recorded under D4.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on; every figure comes from loading the revisions through the registry authority.
