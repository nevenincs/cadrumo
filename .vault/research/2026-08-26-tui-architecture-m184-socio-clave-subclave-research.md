---
tags:
  - '#research'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ecba45f5db5889a9a762e9ee27f267a3400f8b0117109da923fc20daed9f076c'
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

### The diseño's own LIRPF art. 24.2 citation does not match the bundled article's subject

The bundled `ley-35-2006.html.extracted.md` carries "Artículo 24. Rendimiento en caso de
parentesco" (a related-party imputed-rent rule), not a capital-mobiliario reduction. The
diseño cites "artículo 24.2 de la Ley IRPF" for the clave-A/subclave-02 reducción. Article
23 (Gastos deducibles y reducciones) and article 32 (Reducciones) exist and are
plausible matches for their respective claves (C and D) by subject, but article 24 does
not read as the capital-mobiliario reduction the diseño describes. This was NOT resolved
here: either the diseño's citation is to a since-renumbered or repealed provision (the
diseño text bundled is from the "2025-y-siguientes" filing-year edition and may carry a
stale cross-reference), or the actual reducción for clave A/subclave 02 lives elsewhere
in Título II (e.g. a reduction on rendimientos irregulares under a different article) and
the diseño's own numbering is imprecise. The ADR must not adopt "art. 24.2" as a
`legal_refs` entry without a further, dedicated legal cross-check — flagging rather than
guessing, per the standing grounding caution against trusting a single source's numbers.

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

### What was not investigated

- The exact current-year text of LIRPF arts. 23, 24 and 32, and Reglamento IRPF art.
  30.2ª, was read only from the single bundled consolidated file; no live BOE
  cross-check was performed (network access was not exercised in this pass).
- The operator-facing profile input design for a clave/subclave-scoped income line (how
  an operator would declare "this member has income under clave A and clave D") was not
  designed; this research covers the registry/domain shape only.
- Modelo 210's agrupación axis (S295, already queued separately) was not re-examined
  here; it is a distinct investigation per the plan's own split.

## Sources

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_184/files/01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf.extracted.md:293,1784-2387`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/01-349-orden-hac-174-2020-de-4-de-febrero-ejercicio-2020-y-siguientes-894-kb-pdf.pdf.extracted.md:396`
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:364,393,549`
- `src/cadrumo/domain/modelos/_row_models.py:329-349`
- `src/cadrumo/application/modelo/_edit_services.py:460-476`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:636-729`
