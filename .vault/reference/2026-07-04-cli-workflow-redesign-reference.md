---
tags:
  - '#reference'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-workflow-redesign` reference: `Modelo 145 fixed-width export layout ground-truth (dr145 v2.0)`

This reference preserves the extractor-grounded ground-truth for the Modelo 145
fixed-width export layout (plan step P03.S13, "Add export layout metadata
grounded in the official record design"). S13 is DEFERRED / collision-blocked at
the time of writing: the export surface was being edited concurrently by another
actor, so this ground-truth is persisted here so whoever completes S13 has a
zero-fabrication starting point. The P03 foundation steps S11/S12/S14/S15 are
landed and green; S13 remains unchecked because it is genuinely incomplete.

## Summary

Modelo 145 is the IRPF *comunicacion de datos al pagador* (art. 88 RIRPF), a
local payer communication, not an AEAT filing. Its official fixed-width record is
the DR145 v2.0 record design (`dr145v20.pdf`, source ref `aeat-dr-145-v20`,
layout authority), a single 610-position record delimited by the `<T145010>` /
`</T145010>` envelope tags.

### Authoritative source and grounding

Every position and length below is read directly from the programmatic record
design extractor `extract_record_design_pdf` over the bundled `dr145v20.pdf`
(the same extractor the Modelo 145 source-catalogue test already exercises;
`total_positions == 610`, first field offset 1 length 9). These are
EXTRACTOR-GROUNDED with zero fabrication. The per-field RENDERING attributes
(padding, justification, `data_type` for the export renderer, `date_format`) are
NOT extractor-grounded: they are best-effort defaults pending an AEAT
worked-example M145 fichero (none is bundled), so treat them as a refinement, not
as verified truth. The structural mirror (position, length, order, gapless
tiling) is the verified part.

### Field table (DR145 v2.0, 59 rows, contiguous positions 1-610)

Format: DR ordinal / offset / length / kind / mapping.

- 01 / 1 / 9 / literal `<T145010>` (envelope open)
- 02 / 10 / 1 / casilla `comunicacion.pagina-complementaria` (page indicator, blank or "C")
- 03 / 11 / 9 / casilla `perceptor.nif`
- 04 / 20 / 40 / casilla `perceptor.primer-apellido`
- 05 / 60 / 40 / casilla `perceptor.segundo-apellido`
- 06 / 100 / 40 / casilla `perceptor.nombre`
- 07 / 140 / 4 / casilla `perceptor.anio-nacimiento`
- 08 / 144 / 1 / casilla `perceptor.situacion-familiar`
- 09 / 145 / 9 / casilla `perceptor.conyuge-nif`
- 10 / 154 / 1 / casilla `perceptor.discapacidad-grado`
- 11 / 155 / 1 / casilla `perceptor.discapacidad-ayuda`
- 12-14 / 156 / 8 / casilla `perceptor.movilidad-geografica-fecha` (date; collapses the DR dia/mes/anio triple at 156/2 + 158/2 + 160/4 into one contiguous DDMMYYYY span)
- 15 / 164 / 1 / casilla `perceptor.prolongacion-actividad-laboral`
- 16 / 165 / 4 / casilla `descendiente-1.anio-nacimiento`
- 17 / 169 / 4 / casilla `descendiente-1.anio-adopcion`
- 18 / 173 / 1 / casilla `descendiente-1.discapacidad-grado`
- 19 / 174 / 1 / casilla `descendiente-1.ayuda-movilidad`
- 20 / 175 / 1 / casilla `descendiente-1.computo-entero`
- 21 / 176 / 4 / casilla `descendiente-2.anio-nacimiento`
- 22 / 180 / 4 / casilla `descendiente-2.anio-adopcion`
- 23 / 184 / 1 / casilla `descendiente-2.discapacidad-grado`
- 24 / 185 / 1 / casilla `descendiente-2.ayuda-movilidad`
- 25 / 186 / 1 / casilla `descendiente-2.computo-entero`
- 26 / 187 / 4 / casilla `descendiente-3.anio-nacimiento`
- 27 / 191 / 4 / casilla `descendiente-3.anio-adopcion`
- 28 / 195 / 1 / casilla `descendiente-3.discapacidad-grado`
- 29 / 196 / 1 / casilla `descendiente-3.ayuda-movilidad`
- 30 / 197 / 1 / casilla `descendiente-3.computo-entero`
- 31 / 198 / 4 / casilla `descendiente-4.anio-nacimiento`
- 32 / 202 / 4 / casilla `descendiente-4.anio-adopcion`
- 33 / 206 / 1 / casilla `descendiente-4.discapacidad-grado`
- 34 / 207 / 1 / casilla `descendiente-4.ayuda-movilidad`
- 35 / 208 / 1 / casilla `descendiente-4.computo-entero`
- 36 / 209 / 4 / casilla `ascendiente-1.anio-nacimiento`
- 37 / 213 / 1 / casilla `ascendiente-1.discapacidad-grado`
- 38 / 214 / 1 / casilla `ascendiente-1.ayuda-movilidad`
- 39 / 215 / 2 / casilla `ascendiente-1.convivencia-otros`
- 40 / 217 / 4 / casilla `ascendiente-2.anio-nacimiento`
- 41 / 221 / 1 / casilla `ascendiente-2.discapacidad-grado`
- 42 / 222 / 1 / casilla `ascendiente-2.ayuda-movilidad`
- 43 / 223 / 2 / casilla `ascendiente-2.convivencia-otros`
- 44 / 225 / 17 / casilla `pension-compensatoria.importe-anual` (money)
- 45 / 242 / 17 / casilla `anualidades-alimentos.importe-anual` (money)
- 46 / 259 / 1 / casilla `vivienda-habitual.financiacion-ajena`
- 47 / 260 / 25 / casilla `comunicacion.firma-lugar`
- 48-50 / 285 / 8 / casilla `comunicacion.firma-fecha` (date; collapses DR dia/mes/anio at 285/2 + 287/2 + 289/4)
- 51 / 293 / 25 / casilla `comunicacion.firma-tipo`
- 52 / 318 / 50 / casilla `acuse-recibo.empresa-entidad`
- 53 / 368 / 25 / casilla `acuse-recibo.lugar`
- 54-56 / 393 / 8 / casilla `acuse-recibo.fecha` (date; collapses DR dia/mes/anio at 393/2 + 395/2 + 397/4)
- 57 / 401 / 25 / casilla `acuse-recibo.tipo-firma`
- 58 / 426 / 175 / FILLER (reservado para la Agencia Tributaria) — the ONLY genuinely reserved/blank span; the only place FILLER is legitimate
- 59 / 601 / 10 / literal `</T145010>` (envelope close)

### Design decisions

- The three split DR date triples (movilidad 12-14, firma 48-50, acuse 54-56)
  collapse into one contiguous date casilla each; the export field spans the
  contiguous DDMMYYYY positions and renders byte-identically to the three DR
  sub-fields. A completing pass may instead mirror the three DR sub-fields 1:1 if
  strict field-count parity with the extractor is preferred — both are gapless.
- FILLER is used ONLY for DR row 58 (reservado AEAT). Every other position is a
  real perceptor / communication field and MUST carry a casilla ref so the export
  renders the operator's value; modelling any of them as FILLER would silently
  drop communicated data (no-silent-under-declaration).
- The layout tiles positions 1-610 with no gap and no overlap (verify: sort the
  export fields by offset; each field's `offset + length` equals the next field's
  offset; the last ends at 610, matching the extractor `total_positions`).

### Completing S13 (for the owner)

1. Author `export_layouts/` (a single `format = "fixed_width"` layout id
   `modelo-145-dr-v20-fixed-width`, `source_refs = ["aeat-dr-145-v20"]`, one
   record carrying the fields above). Field kinds: `literal` for the two envelope
   tags, `filler` for row 58, `casilla` for every data field.
- 2. Flip the foundation test's `has_fixed_width_export` from `False` to `True`
  and its `not revision.export_layouts` assertion to expect the single layout id;
  add a gapless-coverage assertion that the export fields tile 1-610 and that
  every non-reserved DR field position is covered by a non-filler field
  (no silent drop), cross-checked against `extract_record_design_pdf`.
- 3. Registry must load clean; commit with explicit pathspec.

The registry loads clean with the 50-casilla model that backs this layout
(verified via a direct `load_modelo_directory` probe: 50 casillas, no duplicates).
