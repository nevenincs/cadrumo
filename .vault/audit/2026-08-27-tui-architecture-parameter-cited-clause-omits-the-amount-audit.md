---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:10a813e551c6f79cc636fd870f607bfd816070f840b6d549b0f69430efa5d90e'
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

## Correction: the counts above were measured with a brittle matcher

The figures in "What was checked" (333 verified / 92 partial / 20 none) came from
a STRING matcher that rendered Spanish number formats and searched for them. It
carried a defect: its negative lookahead rejected a match followed by a comma, so
an encoded `12450` never matched a corpus writing "12.450,00". Bracket bounds are
routinely written with explicit centimos, so the partial bucket was inflated with
false absences.

Re-measured with a FORMAT-AGNOSTIC matcher that parses every numeric token in the
corpus into a Decimal set and compares values:

| bucket | count |
|---|---|
| every encoded number is stated in the cited corpus | 335 |
| some legislated numbers absent | 86 |
| only the derived `fixed_addition` absent (expected) | 12 |
| no legislated number stated | 12 |

The error was conservative -- it under-counted verified parameters -- and every
finding above was hand-verified against the corpus text, so none of them changes.
Probe: `numeric_match.py`. Prefer numeric comparison over string rendering for any
future corpus check.

## Checked and found SOUND this pass

- **`renta-{2024,2025}-imputacion-inmobiliaria-year-days = 365`.** This looks like
  a leap-year defect: 2024 had 366 days, the M210 IRNR path uses a leap-aware
  `_m210_days_in_filing_year`, and dividing a part-year holding by 365 instead of
  366 would over-impute. It is NOT a defect. The bundled *Manual práctico de Renta
  2024* -- the leap year itself -- works both imputación examples with 365
  ("1,1 por 100 s/(50% x 105.000) x 62 ÷ 365" and "(2% s/30.500) x (317 ÷ 365)"),
  and every ÷366 in that manual belongs to the intereses de demora chapter, whose
  formula is explicitly "(nº de días) ÷ 365 o 366". 365 is AEAT's own convention
  for this computation and the cited `required_text` quotes the example verbatim.
  Recorded because "correcting" it to 366 would introduce a real defect.
- **`lirpf-art-85:catastral-revision-lookback-years = 10`** -- art. 85 states "diez
  períodos impositivos anteriores", in words.
- **`renta-2025-ric-materializacion-plazo-anos = 3`** and
  **`renta-2025-ric-mantenimiento-plazo-anos = 5`** -- Ley 19/1994 art. 27.4 states
  "tres años" and "cinco años", in words.
- **`renta-2025-ric-reduccion-rate-maximo = 80`** -- art. 27.15 states "el ochenta
  por ciento", in words. The figure is grounded.

A numeric matcher cannot see a number spelled in words, so these four were
absences of the probe, not of the grounding.

## New, low severity: the RIC 80 % is unconsumed and misnamed for what it limits

`renta-2025-ric-reduccion-rate-maximo` has NO formula consumer -- the only
reference outside its own definition is a drift-detection test. Nothing computes
with it today, so it cannot mis-calculate now.

It is still worth an owner's attention, because the name and unit describe a
different rule from the one the article states. The parameter reads as a maximum
*reduction rate*, and its `required_text` names "rendimiento neto"; art. 27.15
makes the eighty percent a **límite on the deducción en la cuota íntegra**
proportionally corresponding to the Canarias rendimientos, not a reduction applied
to the rendimiento neto. Whoever wires this parameter to a formula will read the
name, and the name points at the wrong operation.

This is also an instance of the unreachable-rung class: a rate parameter no
formula reads.

## Sharper statement of the autonomic-scale finding

The 86 partial matches are almost entirely the autonomic scale tables recorded in
`2026-08-26-tui-architecture-autonomic-scale-delegating-article-audit`. Their
partial grounding is an artefact worth naming: their only `legal_ref` is
`ley-35-2006:art-74`, whose `corpus_ref` is the whole consolidated LIRPF, which
contains the STATE scale bounds (12.450, 20.200, 35.200). Those coincide with
several regions' bounds and match by accident. The region-specific bounds and
every autonomic marginal rate do not appear at all.

So the tables are not partially grounded. They are ungrounded, with incidental
overlap from a different scale in the same file.
