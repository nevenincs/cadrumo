---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:9982a73eb00f0e07727cce8495b151622de550fa372e0e7427ec05d8d07e607b'
related: []
---

# `tui-architecture` audit: parameters whose cited clause omits the amount

## What was checked

`aeat-calculation-grounding` requires a value's cited provision to be
"consistent with the value -- the corpus clause states the number encoded". A
probe rendered every encoded number the way Spanish legal text writes it (comma
decimals, dot-grouped thousands, the value both as written and as a percentage,
centimos padded) and searched the cited provision's bundled corpus text for it.

Of 458 numeric parameters, **333 have every encoded number present verbatim in
their cited corpus text**. That is the strongest grounding evidence collected so
far and is recorded here so it is not re-derived.

92 have some numbers present and some absent -- expected for bracket tables,
where derived `fixed_addition` cumulants need not appear in the statute. 20 have
no encoded number anywhere in the cited corpus; those are the subject below.

## The class

A parameter's `legal_refs` chain resolves to a provision whose text does not
state the amount the parameter encodes, while the amount itself is verified
through some other channel. The value is right; the legal chain does not reach
it. These are citation defects, not numeric ones -- the distinction is kept
deliberately, because conflating them would overstate every entry here.

### Repaired

`modelo-347-tercero-anual-threshold-eur` (both revisions) cited
`orden-eha-3012-2008:art-1`, which approves the modelo and states no figure; its
bundled excerpt contains no such number, only dates. RGAT `rd-1065-2007:art-33`
fixes the amount, was already catalogued and corpus-backed, and its own note and
`required_text` pin "3.005,06 euros durante el año natural" verbatim. Its window
(2008-01-01, open) covers both revisions. Added as the establishing provision and
the file comment corrected in `6bbc14045e`; the registry still loads.

### Open -- no in-repo provision states the amount

`modelo-360-quarterly-refund-threshold-eur` (400,00) and
`modelo-360-annual-refund-threshold-eur` (50,00) cite
`orden-eha-789-2010:art-4`, which the catalogue's own note describes as the
**plazo de presentación** article -- a filing deadline. Its corpus contains
neither figure. The establishing provision is the LIVA art. 119 minimum
transposing Directive 2008/9/CE art. 17, which is **not catalogued and not
bundled**, so no repair is possible without fetching official text.

Direction matters here: these thresholds *refuse* a refund below them. An error
denies a taxpayer money they are owed -- the over-payment direction that, per
`no-silent-under-declaration`, nothing in this apparatus watches.

`modelo-232-related-party-threshold-eur` (100.000,00) cites `rd-634-2015:art-13`,
the framework documentation article for operaciones vinculadas, whose bundled
text does not state the figure.

### Open -- year-mismatched legal chain

`renta-2022-minimo-descendientes-madrid-{primer-hijo,segundo-hijo,menor-tres-anos}`
encode 2.498,40 / 2.810,70 / 2.914,80 and cite `madrid-dl-1-2010:art-2`, whose
single `corpus_ref` is the **2025** Renta manual extraction. That file states
2.575,85, the later figure, and none of the 2022 amounts.

The figures themselves ARE cross-checked: each parameter's `source_citations`
names `aeat-renta-2022-manual-parte1` with the exact 2022 string. So one
catalogue entry with one corpus_ref is serving six filing years whose amounts
differ, and only the source-citation channel is year-correct. The 2023, 2024 and
2025 siblings pass precisely because the pinned corpus is their year.

### Not yet examined

`m303-modulos-iva-dificil-justificacion-forfait` (six revisions),
`renta-2025-ric-*` (three), `renta-{2024,2025}-imputacion-inmobiliaria-year-days`
(365) and `lirpf-art-85:catastral-revision-lookback-years` (10). Several are
likely structural constants rather than legislated amounts; each still needs
reading before being called sound.

## Remediation

For M360 and M232, catalogue the provision that fixes the amount and point its
`corpus_ref` at official text -- taking the LAST version from any consolidated
payload, asserting the amending norm, and never passing legal text through a
shell. For the Madrid 2022 rows, the catalogue needs a per-year pinned entry in
the same shape the LIRPF art. 66/76 redactions already use.

Do not resolve any of these by weakening the `required_text` or by pointing at a
closer-but-still-silent article: a citation that does not state the number is the
defect, and a looser one hides it.
