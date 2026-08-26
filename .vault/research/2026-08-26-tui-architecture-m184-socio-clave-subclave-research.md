---
tags:
  - '#research'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c36cc05a907858a835909baac0ce4b45bdca441ffae31bd3146ffe07350b104a'
related: []
---

# `tui-architecture` research: `modelo 184 socio record clave/subclave repetition axis`

## Findings

### The socio record repeats per (member, clave, subclave), not per member

The bundled diseño de registro states, verbatim, at both the entidad record and the
socio record: "Se consignará un registro por cada clave o subclave de rendimientos,
deducciones o retenciones atribuibles para los que se haya consignado un importe y
país." One socio member with income under two claves needs two physical records, each
with its own clave, subclave, importe, reducción and clave-conditional sub-block.
`Modelo184MemberRow` models one row per member and carries no clave/subclave field at
all, so no amount of adding scalar fields to the existing shape can express this; the
row's own identity is missing an axis.

### The remaining fields are conditional on clave and subclave, not flat per-member facts

Full field-by-field inventory against the socio record's field list (positions 76-229):

- Always present per (member, clave/subclave) row: tipo-hoja (constant), codigo-provincia,
  clave-pais, clave-tipo-participe, miembro-a-31-diciembre, dias-miembro,
  porcentaje-participacion, clave, subclave, importe, domicilio-fiscal,
  representante-fiscal-nif (conditional on the MEMBER being a minor or non-resident, not
  on clave).
- Clave A, subclave 02 only: reduccion, citing LIRPF art. 24.2 in the diseño's own text.
- Clave C only: reduccion (diseño cites LIRPF arts. 23.2/23.3), naturaleza-inmueble,
  situacion-inmueble, referencia-catastral (only when situacion-inmueble is 1/2/3),
  clave-declarado, porcentaje-titularidad-inmueble, dias-arrendamiento.
- Clave D only: reduccion (diseño cites LIRPF art. 32); provisiones-gastos-dificil-
  justificacion additionally requires the ENTITY's own tipo-2 record to carry clave "D"
  and régimen "2" (diseño cites Reglamento IRPF art. 30.2ª), and is a computed formula
  (5% of the entity's net yield, times the member's own share percentage, capped at
  EUR 2,000) rather than a raw operator input.
- Clave D, subclave 03 only: rendimiento-neto-previo-eo.
- Clave D, subclave 04 only: rendimiento-neto-minorado-agricola-eo (signed field).
- Clave E: importe only, and the diseño states it applies only to members who are IS or
  IRNR-with-establecimiento-permanente taxpayers — a member-level eligibility test this
  tree does not currently model anywhere.
- Clave F/G, subclave 01/02: importe means ganancias vs. pérdidas, same field different
  meaning by subclave.
- Clave I/J/K: importe is a deduction base/amount or retención; subclave-enumerated
  (6/4/5 members respectively); no reduccion or inmueble fields apply.

### Legal citation cross-check, resolved

All four citations were read in full against the bundled consolidated texts (not
excerpted, not taken on the diseño's word):

- **LIRPF art. 23.2/23.3 (clave C reducción) — CONFIRMED correct.** Art. 23.2 is the
  arrendamiento-vivienda reduction (90/70/60/50%); art. 23.3 is the >2-year or
  notoriamente-irregular 30% reduction capped at EUR 300,000/year. Both are genuine
  capital-inmobiliario reductions matching the diseño's clave-C usage.
- **LIRPF art. 24.2 (clave A/subclave 02 reducción) — CONFIRMED WRONG.** Art. 24 is
  "Rendimiento en caso de parentesco" (a related-party imputed-rent rule), one paragraph,
  no numbered subsections at all — it cannot be the reduction the diseño describes. The
  correct provision is **LIRPF art. 26.2**: "Los rendimientos netos previstos en el
  apartado 4 del artículo 25 de esta Ley con un período de generación superior a dos
  años... se reducirán en un 30 por ciento... [capped at] 300.000 euros anuales." This
  is an exact match: clave A/subclave 02 is itself defined in the diseño's own subclave
  table as "Rendimientos del capital mobiliario previstos en el apartado 4 del artículo
  25 de la LIRPF" — so art. 26.2's cross-reference to "apartado 4 del artículo 25" lines
  up precisely with the subclave the reducción field is conditioned on. The diseño's
  "24.2" is a citation error (most likely a transcription slip between the visually
  similar "26" and "24"); the ADR must ground this field on **art. 26.2**, not art. 24.2.
- **LIRPF art. 32 (clave D reducción) — CONFIRMED correct.** "Reducciones" for
  rendimientos de actividades económicas, including the same >2-year/irregular 30%
  reduction (apartado 1) alongside the reduced-workload reductions (apartado 2). The
  diseño does not specify which apartado; apartado 1 is the one structurally analogous to
  arts. 23.3/26.2, so the ADR should cite art. 32.1 specifically rather than the bare
  article.
- **Reglamento IRPF (RD 439/2007) art. 30, regla 2ª (provisiones-gastos) — CONFIRMED
  correct, verbatim.** `rd-439-2007-art-30.html.extracted.md`: "El conjunto de las
  provisiones deducibles y los gastos de difícil justificación se cuantificará aplicando
  el porcentaje del 5 por ciento sobre el rendimiento neto, excluido este concepto, sin
  que la cuantía resultante pueda superar 2.000 euros anuales." Both the 5% and the EUR
  2,000 cap are exact matches to the diseño's description and to this research's own
  restatement of the formula — the numeric values the grounding rule specifically flags
  for cross-check are verified against live bundled text, not merely restated from the
  diseño.

No further legal cross-check is outstanding for these four citations. The ADR should cite
`ley-35-2006.html` arts. 23.2, 23.3, 26.2 (NOT 24.2) and 32.1, and `rd-439-2007-art-30.html`
regla 2ª.

### M349 already models an equivalent axis correctly; M347 and M232 do not have it

M349's own diseño (`disenos_registro/modelo_349/files/01-349-...pdf.extracted.md:396`)
states "consignar un único registro por cada clave de operación y periodo" — the same
shape (operator, clave, periodo) as M184's (member, clave, subclave). `Modelo349OperadorRow`
(`src/cadrumo/domain/modelos/_row_models.py:329`) already carries `clave_operacion` as a
first-class field, so its row identity was built including the clave axis from the start.
The S288 edit-contract natural key for the `operador` row kind is already the compound
tuple `("nif_comunitario", "clave_operacion")`
(`src/cadrumo/application/modelo/_edit_services.py:463`), proving the whole-set-replacement
mechanism already supports a compound key without modification — only the tuple for the
`miembro` row kind (currently `("nif",)`, `_edit_services.py:461`) needs to widen.

M347's contraparte diseño (`disenos_registro/modelo_347/files/01-347-...pdf.extracted.md`)
and M232's vinculada diseño (`disenos_registro/modelo_232/files/01-232-...xlsx.extracted.md`)
were both searched for the same "por cada clave" phrasing and neither carries it — both
repeat purely per-counterparty/per-vinculada, with no second axis. This is not a
detail-row-family-wide problem.

### S288 ripple, addressed explicitly

S288 ruled whole-set replacement by natural key (never a minted or positional identity),
proven generically at `detail_row_natural_key` (`_edit_services.py:470-476`), which already
joins an arbitrary tuple of the row's own declared fields. Widening `Modelo184MemberRow`
to carry `clave`/`subclave` and widening `_DETAIL_ROW_NATURAL_KEY_FIELDS["miembro"]` to
`("nif", "clave", "subclave")` is additive under the existing mechanism — the same shape
349's `operador` key already takes. Whole-set-replacement-by-natural-key and
absence-as-deletion both survive unchanged; only the key's arity widens. No other part of
S288's contract (detail_row_intents, ADD/UPDATE/DELETE, MOVE_ROW's retirement) depends on
the row kind's specific field set.

### The M347 contraparte row already carries a clave field without the record repeating on it

`Modelo347ContraparteRow` carries `clave_operacion` on the row, but M347's own diseño
declares no per-clave repetition axis for the contraparte record (confirmed above). So a
row carrying a clave-shaped field is not itself evidence that a record repeats on that
axis — 349's row repeats per clave because its diseño says so; 347's row carries a clave
value as one fact among several on an otherwise flat per-counterparty record. The ADR
should not treat "does the row have a clave field" as the test; the test is what the
record's own diseño states about repetition.

### What was not investigated

- No live BOE cross-check was performed beyond the bundled consolidated corpus files
  (network access was not exercised in this pass); the bundled `ley-35-2006.html` and
  `rd-439-2007-art-30.html` were read as the authoritative texts per the standing
  bundled-corpus-first grounding rule.
- The operator-facing profile input design for a clave/subclave-scoped income line (how
  an operator would declare "this member has income under clave A and clave D") was not
  designed; this research covers the registry/domain shape only.
- Modelo 210's agrupación axis (S295, already queued separately) was not re-examined
  here; it is a distinct investigation per the plan's own split.

## Sources

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_184/files/01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf.extracted.md:293,1784-2387`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/01-349-orden-hac-174-2020-de-4-de-febrero-ejercicio-2020-y-siguientes-894-kb-pdf.pdf.extracted.md:396`
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:364-397,457-464,549-564`
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-30.html.extracted.md`
- `src/cadrumo/domain/modelos/_row_models.py:329-349,598-621`
- `src/cadrumo/application/modelo/_edit_services.py:460-476`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:636-729`
