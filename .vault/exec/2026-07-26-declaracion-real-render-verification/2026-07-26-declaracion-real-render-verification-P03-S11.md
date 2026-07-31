---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:87d7231061ed9eece948d52772e68157b395710838f083f560e1d68050b3fcb7'
step_id: 'S11'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Widen every label pattern for which a bundled render evidences the wording, inventing none

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390`

## Description

The widening itself landed earlier in this campaign, when the Modelo 390 real
render was first read. This Step confirms it is complete against the whole
corpus, and bounds what "complete" can mean when the evidence is one document.

The corpus was swept for renders in a language other than Spanish: all 76 bundled
PDFs, classified on their page-one header. Exactly one is not Spanish, the Modelo
390 `2021-0A` justificante, and it is the one already exploited. So no other
profile can be widened on evidence, and none was.

Within that render, the widening is at the limit of what it evidences. Its four
`named_label` targets whose lines the document carries are all widened and all
match: boxes 64, 65, 97 and 662. The fifth, `iva.anual.cuota-devengada-total` at
box 47, is not widened and must not be -- the render prints form pages 1, 3, 4 and
6, and box 47 sits on the omitted page 2, so no English wording for it is
observable in any bundled evidence.

## Outcome

Four patterns widened, one deliberately left, nothing invented.

Each alternate is the label as the English document literally prints it: `Total
deductions` for box 64, `Result of the general system (47 - 64)` for box 65, `To
offset` for box 97, and `Amounts pending offset arising in the year` for box 662.
The Spanish branches are unchanged and the Spanish facsimile is unregressed,
still reading 88.416,00 / 68.202,00 / 20.214,00 / 2.226,00 / 2.106,00.

Coverage on the English render went from 0.1000 to 0.4000, recovering three
printed and populated boxes that were being silently dropped. Box 662 became
reachable with them and is printed blank, which is how this render came to
exercise the blank-box guard end to end for the first time on real evidence.

The falsifiability of the widening was proven rather than assumed: reverting the
single `Total deductions` alternate fails the extracted-set assertion for this
specimen, naming `iva.anual.cuota-deducible-total` as unexpectedly absent, with
the other cases still green.

## Notes

This Step closes with 154 targets across 19 profiles still exposed, and that is
the correct outcome rather than an incomplete one. Widening any of them would
mean authoring wording no bundled document prints, which is the failure mode the
campaign exists to correct -- a profile claiming to read text the form does not
carry. Those profiles are registered as evidence gaps under D3 instead, and the
structural question of whether hand-authored alternates are the right shape at
all is assessed separately.

The one-render limit is worth stating plainly for a future reader: the exposure
measurement is complete and estate-wide, while the remediation is bounded by a
single specimen. Those two facts are easy to conflate into a false impression
that the language route has been dealt with. It has been measured, and it has
been fixed for one modelo.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on.
