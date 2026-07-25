---
tags:
  - '#research'
  - '#declaracion-profile-printed-box-scope'
date: '2026-07-25'
modified: '2026-07-25'
related: []
---

# `declaracion-profile-printed-box-scope` research: `M303 printed-form census against the AEAT manual annex`

The Modelo 303 `declaracion_pdf` extraction profile refuses every real AEAT
render. Six of its eighteen targets carry `named_label` patterns that match only
text the project's own fixture generator prints. The question this census
answers is narrow and factual: for each of those six targets, what does the
official AEAT form actually print, and can the target be re-pointed at it?

The answer is that four of the six cannot. Two have no evidence anywhere in the
specimen, one has no printed box at all, and one is identified by the value of a
neighbouring cell rather than by any fixed position or label. The remaining two
are re-pointable, but one of them collides with a box the same profile already
targets. The measurement therefore reframes the problem: this is not six wrong
strings, it is six casillas the printed document does not separately carry.

## Findings

### The specimen is an unmodified AEAT publication, not a project artefact

The census ran against `src/cadrumo/tests/fixtures/manual_annexes/303/source-Cap_9_303_es_es.pdf`,
the twelve-page ANEXO of the AEAT Manual Práctico IVA 2024 chapter 9, landed at
commit `cdeeaa293c`. It carries four fully worked Modelo 303 declarations for
the manual's *supuesto práctico*, rendered by the AEAT publication toolchain
(`Adobe InDesign 19.1`, `Adobe PDF Library 17.0`) and declared
`provenance: aeat_published_facsimile`, `role: casilla_value_oracle` in its
sidecar. Per-quarter splits are at `manual_annexes/303/2024-1T` through `2024-4T`.

Both layers were used deliberately. Every structural claim below (the row
census, the autoconsumo absence) was measured against the unmodified twelve-page
source, because the splitting operation rewrote the PDFs. The per-quarter
coverage numbers were measured against the splits, which is what they are for.

### Real-render coverage is 12/18, 11/18, 11/18, 10/18 — not a single figure

Running the production classifier (`_classify_target`,
`src/cadrumo/adapters/inbound/declaracion/_parser.py:548`) over each quarter with
the live registry profile gives:

| quarter | covered | additional misses beyond the six |
| --- | --- | --- |
| 1T | 12/18 | — |
| 2T | 11/18 | `iva.compensacion-aplicada-periodo` (box 78) |
| 3T | 11/18 | `iva.compensacion-aplicada-periodo` (box 78) |
| 4T | 10/18 | box 78, and box `37` |

The profile declares `min_coverage = "1"` with `failure_semantics = "fail_hard"`,
so every quarter is refused. The degradation beyond the six is caused by
genuinely **blank** boxes: a blank box's line terminates on its own printed box
number with no value following. This is the same class the annex sidecar records
as unreachable from the generated corpus, reproducing here independently.

### The rate is entered data, not printed text — so the 21% row has no fixed address

The form prints six rate-generic base/tipo/cuota triples for IVA devengado
régimen general: `(150,151,152)`, `(165,166,167)`, `(01,02,03)`,
`(153,154,155)`, `(04,05,06)`, `(07,08,09)`. None is labelled with a rate. The
rate is a value the filer enters into the middle box of the triple.

A census of every filled triple across all twelve pages returns exactly eight
rows, and only two distinct triples are ever used:

```
base[07]=83.000,00   tipo[08]=21,00  cuota[09]=17.430,00
base[22]=24.000,00   tipo[23]=5,20   cuota[24]=1.248,00
base[07]=91.000,00   tipo[08]=21,00  cuota[09]=19.110,00
base[22]=12.000,00   tipo[23]=5,20   cuota[24]=624,00
base[07]=94.200,00   tipo[08]=21,00  cuota[09]=19.782,00
base[22]=24.000,00   tipo[23]=5,20   cuota[24]=1.248,00
base[07]=102.000,00  tipo[08]=21,00  cuota[09]=21.420,00
base[22]=12.000,00   tipo[23]=5,20   cuota[24]=624,00
```

The triples `(165,166,167)`, `(01,02,03)`, `(153,154,155)`, `(04,05,06)` and
`(19,20,21)` are blank in every quarter.

This settles the addressing question for `iva.repercutido.general`. Binding it
to box `09` would encode that *this* filer entered 21% into the third triple.
A filer using `(01,02,03)` for the same rate extracts blank. The correct
address is conditional on a sibling cell's value, which `match_strategy` cannot
express: it is a closed three-member Literal
(`src/cadrumo/domain/calculations/registry/_schema_extraction.py:59`), and the
`bbox_anchored` member's `column_anchor` constrains an x-range, not a
sibling-value predicate.

### Modelo 390 solves the same shape only because its rows are rate-fixed

The M390 profile binds its analogous primitives with `bbox_anchored` anchors on
`^02$`, `^04$`, `^06$` for super-reducido, reducido and general respectively.
That works because M390's annual worksheet assigns each rate a fixed row
position. M303's do not. The contrast is why the M390 precedent does not
transfer, and it is worth stating explicitly so a future reader does not reach
for it.

### Two of the six have no evidence in the specimen at all

`iva.repercutido.reducido` (10%) and `iva.repercutido.super-reducido` (4%) are
never exercised. Every rate row other than the 21% and recargo rows is blank
across all four quarters. Any pattern authored for them would be invention
rather than grounding.

### `autoconsumo` does not appear on the AEAT form

A case-insensitive search for `autoconsumo` across all twelve pages of the
official form returns **zero** occurrences. Autoconsumo is declared inside the
ordinary régimen general base rows; AEAT prints no separate box for it. There is
no text for `iva.autoconsumo.promotor.base` to be re-pointed at.

### The two re-pointable targets, one of which collides

`iva.autorepercutido.intracomunitaria` maps to printed box `11` (its base is
box `10`). It is blank in 4T.

`iva.soportado.interiores` maps to printed box `29`. The same profile already
carries a separate target for casilla `29` with pattern
`Por\s+cuotas\s+soportadas\s+en\s+operaciones\s+interiores\s+corrientes`.
Re-pointing therefore produces two casilla ids reading one printed box.

### The generator's own comment records the cause

`src/cadrumo/tests/fixtures/justificantes/_generate_iva_corpus.py:488` states that
the labels carry the `Primitivo` prefix *"to avoid collision with the form-page
totals (box 27 ..., box 29 ...)"*. The prefix exists to manufacture a
distinction the real document does not have. On the printed form
`iva.soportado.interiores` **is** box 29; the collision the prefix avoids is not
an accident of naming but the fact itself.

### The originating decision assumed the printed form matches the diseño de registro

`2026-06-02-m303-parser-engine-totals-impedance-adr` chose Route A — the parser
extracts primitives, the engine recomputes totals — and listed the risk in its
own Forces section: *"not all M303 PDFs expose primitives in extractable form.
The `iva.repercutido.general / reducido / super-reducido` triple is
operator-supplied per AEAT diseño-de-registro"*. That sentence contains the
error. The primitives are indeed fields of the **electronic submission record**;
they are not separately printed on the **PDF form**. The risk was resolved by
changing the fixtures rather than by testing a real render.

`2026-06-03-m303-synthetic-generator-primitive-spec-adr` then directed that the
generator *"must print those primitive line items on the M303 fixture pages so
the parser has something to extract"* — the causality inverted: the document was
shaped to fit the profile.

`2026-06-03-synthetic-fixture-primitive-encoding-discipline-adr` asserts as a
force that *"the PDF generator prints both the primitives and the summed totals
on the same page"*. Measured against the real form this is half-true in the
way that matters: the per-rate **rows** are printed, but positionally, with the
rate identity living in an entered value — and autoconsumo is not printed at all.

That discipline's underlying anti-tautology argument is nonetheless sound and is
not disturbed by this census: a fixture that encodes only a total and asserts the
engine reproduces it consumes its own input. What the census challenges is the
*encoding* the discipline was satisfied by, not its purpose.

### Blast radius if the six are dropped

15 synthetic M303 corpus fixtures
(`_MODELO_303_CORPUS_FIXTURES`, 2021-2T through 2024-4T); 48 expected-value
entries across 8 fixture blocks in
`src/cadrumo/adapters/inbound/declaracion/tests/_parser_boundary_m303_current_expected.py`;
3 parser-boundary test modules; roughly 24 modules referencing the six casilla
ids, of which most consume them as engine casillas on the calculate path and are
unaffected by an extraction-scope change.

### What was not investigated

Whether a structured triple-reading strategy (locate a base/tipo/cuota row,
read the tipo as data, attribute the cuota to the matching rate) is worth adding
to `match_strategy`. The real form does print the information such a strategy
would need, so the capability is not impossible — only inexpressible today. No
specimen exercising the 10% or 4% rows was located, so such a strategy could not
currently be verified for those rates even if built.

Whether the reconcile path can satisfy the engine's primitive-summation formulas
from printed totals once the six are dropped. This is the impedance Route A was
created to resolve and it reopens under any option that removes primitive
extraction; it is the substantive question the ADR must settle.

## Sources

- `src/cadrumo/tests/fixtures/manual_annexes/303/source-Cap_9_303_es_es.pdf` (and its `.json` sidecar), landed at commit `cdeeaa293c`
- `src/cadrumo/tests/fixtures/manual_annexes/303/2024-1T.pdf` through `2024-4T.pdf`
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/IVA_2024/Imagenes/Cap_9_303_es_es.pdf
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml:1-155`
- `src/cadrumo/domain/calculations/registry/_schema_extraction.py:48-80`
- `src/cadrumo/adapters/inbound/declaracion/_parser.py:548`, `:630-694`, `:935-977`
- `src/cadrumo/tests/fixtures/justificantes/_generate_iva_corpus.py:171`, `:478-530`
- `src/cadrumo/adapters/inbound/declaracion/tests/_parser_boundary_m303_current_expected.py`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/extraction_profiles/0001-extraction_profiles.toml:16-22`
