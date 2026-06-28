---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
  - "[[2026-05-21-taxpayer-type-applicability-research]]"
---

# `cli-workflow-redesign` adr: `The corporate-entity calculation model — a legal entity is routed to the Impuesto sobre Sociedades schedule (Modelo 200/202, LIS rate scale), an attribution entity to member pass-through, and never to the IRPF tarifa` | (**status:** `accepted`)

## Problem Statement

The parent ADR `2026-05-21-taxpayer-type-applicability-adr` adds a
typed `entity_type` axis to the profile and derives modelos,
calendar, calculations and brackets from it. Its plan
`2026-05-21-taxpayer-type-applicability-plan` requests a child ADR
to adjudicate the *corporate-entity calculation model* before
W02.S08 (calculation/bracket derivation) and W03.S13 (per-entity
rate schedules) can land.

A *sociedad limitada*, *sociedad anónima*, *cooperativa*, *sociedad
civil con objeto mercantil* and other legal entities are
contribuyentes del **Impuesto sobre Sociedades** (IS), Ley 27/2014
LIS (BOE-A-2014-12328) — not IRPF taxpayers. They file **Modelo 200**
(annual IS self-assessment) and **Modelo 202** (pago fraccionado),
on a corporate calendar, against an entirely different rate schedule
(LIS Art. 29), and never file Modelo 100 or Modelo 130. An
*attribution entity* (comunidad de bienes, sociedad civil sin objeto
mercantil) is neither an IS nor an IRPF taxpayer in its own right —
its income is attributed to and taxed in the members' hands.

The engine today has no way to route on entity type: every profile
is treated as an autónomo and offered the IRPF tarifa. This child
ADR fixes *how a legal-entity or attribution-entity profile reaches
the correct calculation path*. The entity-type fact itself is added
by the parent ADR's Wave 1; this ADR owns the routing it enables.

## Considerations

- **The IS calculation chain is structurally distinct from IRPF.**
  Modelo 200 runs `resultado contable → ajustes (correcciones LIS
  Arts. 12-26) → base imponible → tipo de gravamen (Art. 29) → cuota
  íntegra (Art. 30) → deducciones (Arts. 31/32/36/39) → cuota
  líquida → pagos fraccionados/retenciones (Art. 41)`. The IRPF
  Modelo 100 chain is unrelated. They cannot share a bracket
  resolver.
- **The registry IS grounding is already substantial.**
  `legal/is.toml` carries reviewed, BOE-keyed entries for LIS
  Arts. 12, 13, 15, 16, 18, 19, 21, 22, 25, 26, **29** (rates),
  **30** (cuota íntegra), 31, 32, 36, 39, **40** (pago fraccionado),
  41, **100**, **105** (reserva de nivelación), 124 (declaration
  deadline), plus RIS RD 634-2015 Arts. 3/13. Modelo 200
  (`revisions/2024-y-siguientes`) and Modelo 202
  (`revisions/2025-y-siguientes`, `2023-2024`, `2019-2022`) carry
  casillas, formulas, export layouts and source citations. This ADR
  decides routing *to* that grounding; it does not re-ground it.
- **Rate dispatch is partly scaffolded but not wired.** Modelo 200
  `records/parameters.toml` already declares entity-type-dispatched
  tipo-gravamen parameters (`is.modelo-200.tipo-gravamen-general`,
  `-pyme`, `-new-entity-first-2-years`, `-cooperative-protected`,
  `-non-profit-special-regime`), each carrying `ley-27-2014:art-29`
  `legal_refs`, and a comment names a `lookup_parameter_by_entity_type`
  op that "no formula consumes today". The cuota-íntegra formula
  (`modelo-200-cuota-integra`, `[00562] = [01330] x [00558]/100`)
  multiplies the base by a casilla-supplied rate, not by a
  dispatched parameter. Routing the entity-type fact into that
  dispatch is the open wiring.
- **Attribution entities are a pass-through, not a calculation.**
  Régimen de atribución de rentas (LIRPF Title X Section 2) means
  the entity computes and *attributes* income — its members file the
  substantive tax (IRPF, IS or IRNR). The entity's own filing is the
  informational **Modelo 184** (Orden HAP/2250/2015, grounded in
  `legal/atribucion-rentas.toml`). The engine must not run an IS or
  IRPF cuota for an attribution entity.
- **A wrong tax is worse than an incomplete answer.** Per the
  parent ADR's "default must be safe" constraint, routing must be
  explicit: an undeclared or unsupported entity form yields an
  `incomplete` verdict, never a defaulted IRPF or IS calculation.

## Constraints

- Every regulatory claim is grounded in BOE / AEAT authority. The
  LIS articles cited here all resolve to existing reviewed
  `legal/is.toml` entries (`document_id = "BOE-A-2014-12328"`); no
  new legal behaviour is invented.
- This is an ADR only. It changes no production code and no registry
  data. The schema work belongs to the parent plan's Wave 1, the
  registry rate/calendar data to Wave 3.
- The hexagonal boundary holds: entity-type routing is a domain
  derivation, not an adapter concern. The CLI root surface stays
  `config` / `app`.
- Per the calculation-grounding rule, the IS rate scale, the Modelo
  202 modality threshold and the corporate calendar each carry
  `legal_refs` when encoded; figures that could not be confirmed to
  BOE-article precision (see Decision §5) are deferred to the
  registry track, not asserted.
- No tautological calculation tests: IS cuota tests derive expected
  values from the AEAT Manual de Sociedades worked examples or
  registry-authoritative fixtures, never by re-applying the rate the
  registry declares.

## Decision / Implementation

Adopt a **three-branch tax-routing model** keyed on the parent ADR's
`entity_type` axis. The branch selects the tax, and the tax selects
the modelos, calendar, calculation chain and rate schedule.

### 1. `is_legal_entity` → Impuesto sobre Sociedades

A legal-entity profile routes to the IS path:

- **Modelos.** Modelo 200 (annual) and Modelo 202 (pago fraccionado)
  become applicable; Modelo 100 and Modelo 130/131 are suppressed
  from the applicability set. Modelo 220/222 apply only to
  fiscal-consolidation groups and are out of scope for this ADR
  (a profile flag, deferred).
- **Calendar.** Modelo 200 is due within 25 calendar days following
  the 6 months after period end — 1-25 July for a calendar-year
  entity (LIS Art. 124, `legal/is.toml` `ley-27-2014:art-124`;
  already registered as the `modelo-200-2024-0a` deadline window).
  Modelo 202 is due in the first 20 calendar days of April, October
  and December (LIS Art. 40, `ley-27-2014:art-40`).
- **Rate schedule.** The cuota íntegra applies the LIS Art. 29 tipo
  de gravamen — *never* the IRPF tarifa. The corporate calculation
  selects its rate by entity sub-form through the
  `lookup_parameter_by_entity_type` dispatch the registry already
  scaffolds (`is.modelo-200.tipo-gravamen-*` parameters). The
  parent ADR's optional `is_legal_entity` sub-form
  (`sl | sa | cooperativa | sociedad_civil_mercantil |
  sin_fines_lucrativos | other`) is the dispatch key; the
  newly-created-entity 15% rate is a period-dependent state
  (first two profit-making periods, LIS Art. 29) carried alongside
  the sub-form, not a sub-form value itself.
- **Calculation chain.** A legal-entity profile is routed to the
  Modelo 200 calculation surface (`resultado contable → correcciones
  → base imponible → cuota íntegra → cuota líquida`), wholly
  distinct from the Modelo 100 chain. Modelo 202's two modalidades
  (Art. 40.2 cuota method, Art. 40.3 base-imponible method) are
  selected per §3 below.

### 2. `attribution_entity` → member pass-through

An attribution-entity profile (comunidad de bienes, sociedad civil
sin objeto mercantil, herencia yacente) routes to the **pass-through
branch**:

- The entity runs **no IS and no IRPF cuota**. Régimen de atribución
  de rentas (LIRPF Title X Section 2): income is attributed to each
  socio/comunero/partícipe and taxed under that member's own tax.
- The entity's only own obligation modelled here is the
  informational **Modelo 184** (Orden HAP/2250/2015, filed in
  February; grounded in `legal/atribucion-rentas.toml`
  `orden-hap-2250-2015:art-1..5`). The Modelo 184 exemption for
  entities with no economic activity and attributed rentas below
  3.000 € (`orden-hap-2250-2015:art-2`) is a registry applicability
  condition.
- The substantive calculation belongs to each member's profile, not
  the entity's. The engine surfaces an explicit
  `attribution_pass_through` verdict — the entity-level "what is my
  cuota" question has the honest answer "none — the income is taxed
  in the members' returns".

### 3. Modelo 202 modality selection

Modelo 202 carries two pago-fraccionado modalidades:

- **Art. 40.2 — cuota method.** Base = cuota íntegra of the last
  filed period; instalment = 18% of that base (LIS Art. 40.2;
  registry parameter `is.modalidad_cuota.percentage`, value `18`,
  cited to `aeat-modelo-202-instructions`).
- **Art. 40.3 — base-imponible method.** Instalment computed on the
  taxable base of the first 3 / 9 / 11 months. **Mandatory** for
  entities whose importe neto de la cifra de negocios (INCN)
  exceeded **6.000.000 €** in the 12 months before the period start
  (confirmed against AEAT "Cálculo pago fraccionado según la
  modalidad regulada en el artículo 40.3 LIS" and the Manual de
  Gran Empresa — see §5); optional for entities below that
  threshold.

The modality is **derived**, not asked twice: above the 6.000.000 €
INCN threshold the engine selects Art. 40.3 and does not offer
Art. 40.2. The INCN threshold becomes a profile fact (or is read
from the prior-period INCN) feeding a registry applicability
condition.

### 4. Engine routing contract

- The parent ADR's `ProfilePredicateDefinition` conditions gain the
  ability to test `entity_type`. Modelo 200/202 applicability,
  calendar and calculation selection are gated on
  `entity_type == is_legal_entity`; Modelo 100/130/131 are gated on
  `entity_type == natural_person` with the actividad-económica
  income category.
- An undeclared `entity_type`, or a recognised-but-unsupported legal
  form, yields an `incomplete` verdict (parent ADR's safe default).
  The engine never runs an IRPF cuota for a company or an IS cuota
  for an attribution entity.

### 5. Grounding status — confirmed vs deferred

**Confirmed in this ADR pass (BOE / AEAT authority):**

- LIS Art. 29 micro-empresa scale: for periods initiated in **2025**,
  17% on the 0-50.000 € tranche and 20% on the rest; for periods
  initiated in **2026**, **19% / 21%** (AEAT Manual de Sociedades
  "Tipos de gravamen vigentes"; AEAT "Tipo de gravamen y cuota
  íntegra" folleto). This resolves research-doc open question 6 for
  2025/2026 and surfaces a **registry defect** — see Consequences.
- Modelo 202 Art. 40.3 modality is **mandatory above an INCN of
  6.000.000 €** in the prior 12 months; the additional-data
  reporting (Anexo I Parte 2) is mandatory at an INCN of
  10.000.000 € (AEAT "Cálculo pago fraccionado según la modalidad
  regulada en el artículo 40.3 LIS"; AEAT Manual de Gran Empresa).
  This resolves research-doc open question 1.

**Deferred to the registry track (not asserted here):**

- The exact LIS Art. 40.3 article wording fixing the 6.000.000 €
  figure must be transcribed against BOE-A-2014-12328 Art. 40 when
  the Modelo 202 applicability condition is encoded.
- Modelo 202 has **no `deadline_windows` and no `filing_schedules`**
  in the registry today (verified:
  `modelos/202/revisions/2025-y-siguientes/` carries no such
  records). The April/October/December corporate fraccionado
  calendar must be registered with `ley-27-2014:art-40`
  `legal_refs` in Wave 3 — it is a calendar gap parallel to the
  parent plan's round-3 R1 finding.
- The Modelo 200 `is.modelo-200.tipo-gravamen-pyme` parameter
  currently holds a single flat value `23` — see Consequences.

## Rationale

Entity type selects the *tax*, and the tax is not a variant of one
calculation — IS and IRPF are different cuotas with different bases,
different rate schedules and different modelos. A tool that runs the
IRPF tarifa for a sociedad limitada produces a confidently wrong
number on a regulated calculation. The fix is structural: route the
profile to one of three explicit branches — IS, IRPF, or attribution
pass-through — before any cuota runs. The IS branch has substantial
registry grounding already (`legal/is.toml`, Modelo 200/202
revisions, the scaffolded rate-dispatch parameters); what is missing
is the *routing* — wiring the entity-type fact to the dispatch and to
the Modelo 200/202 calculation surface. Pulling this into its own
ADR keeps the IS rate schedule, the Modelo 202 modality rule and the
attribution pass-through out of the Wave-2 engine rewrite, where they
would be buried, and gives the owner a single tax-semantics decision
to confirm.

## Consequences

- The corporate-tax wrong-routing defect is closed at its root: a
  legal entity reaches Modelo 200/202 and the LIS rate scale; an
  attribution entity reaches member pass-through; neither touches
  the IRPF tarifa.
- **Registry defect surfaced — `tipo-gravamen-pyme` parameter.**
  `modelos/200/revisions/2024-y-siguientes/records/parameters.toml`
  encodes `is.modelo-200.tipo-gravamen-pyme` as a single flat value
  `23`. LIS Art. 29's micro-empresa rate is a **two-bracket scale**
  (17%/20% for 2025, 19%/21% for 2026), not a flat 23%; the `23`
  figure matches no LIS Art. 29 micro-empresa tranche. The registry
  track must replace this with the bracketed scale (a tranche
  table, like the IRPF tarifa) and add the 2026 19%/21% values,
  each cited to `ley-27-2014:art-29`. Until corrected, no formula
  should consume it. Logged here as a Wave-3 registry action.
- A dependency on the parent plan: the IS branch cannot route until
  Wave 1 adds `entity_type` and its `is_legal_entity` sub-form, and
  cannot compute until Wave 3 supplies the corrected Art. 29 rate
  scale and the Modelo 202 deadline windows / filing schedules.
- The `lookup_parameter_by_entity_type` dispatch op (already named
  in the registry parameter comment, not yet consumed) becomes the
  wiring point for the cuota-íntegra rate; W03.S13 connects it.
- Fiscal-consolidation (Modelo 220/222, régimen de consolidación
  fiscal) is explicitly **out of scope** — a future profile flag
  and a separate adjudication if needed.
- **Owner decision (2026-05-21): accepted.** This ADR makes a
  tax-semantics decision (three-branch routing, IS vs IRPF vs
  attribution pass-through, Modelo 202 modality derivation). The
  owner approved the parent plan and its child ADRs to proceed; the
  parent plan's Wave 1 is landed. The ADR is `accepted`;
  implementation of the IS routing belongs to W02.S08, and the
  corrected Art. 29 rate scale and Modelo 202 calendar to Wave 3.

## Sources

- BOE — Ley 27/2014 LIS (LIS Arts. 29, 30, 40, 41, 124; corpus,
  registry `legal/is.toml`): BOE-A-2014-12328 —
  <https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328>
- AEAT — Manual práctico de Sociedades 2024, "Tipos de gravamen
  vigentes": <https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-sociedades-2024/capitulo-06-liquidacion-is-determinacion-tributaria/cuota-integra-casilla-00562/tipo-gravamen/tipos-gravamen-vigentes.html>
- AEAT — "4.3 Tipo de gravamen y cuota íntegra" (folleto
  actividades económicas, micro-empresa 17/20 % 2025): <https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/folleto-actividades-economicas/4-impuesto-sobre-sociedades/4_3-tipo-gravamen-cuota-integra.html>
- AEAT — Modelo 202, plazo de presentación de los pagos
  fraccionados: <https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/pagos-fraccionados-impuesto-sobre-sociedades/plazo-presentacion-pagos-fraccionados.html>
- AEAT — Cálculo del pago fraccionado según la modalidad regulada
  en el artículo 40.3 LIS (INCN 6.000.000 € threshold): <https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/pagos-fraccionados-impuesto-sobre-sociedades/calculo-pago-fraccionado-segun-modalidad-lis.html>
- AEAT — Modelo 202. Instrucciones 2025 y siguientes: <https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/impuesto-sobre-sociedades/modelo-202-is-i_____resencia-territorio-fraccionado_/instrucciones/Instrucciones-para-2025.html>
- AEAT — Manual de Gran Empresa, pagos fraccionados de Sociedades
  (umbral 6.010.121,04 €): <https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/manual-gran-empresa/son-consecuencias-superar-umbral-6_010_12104/pagos-fraccionados-sociedades.html>
- BOE — Orden HFP/227/2017 (modelos 202 y 222): BOE-A-2017-2778 —
  <https://www.boe.es/buscar/doc.php?id=BOE-A-2017-2778>
- BOE — Orden HAP/2250/2015 (modelo 184, atribución de rentas;
  registry `legal/atribucion-rentas.toml`): BOE-A-2015-11596 —
  <https://www.boe.es/buscar/act.php?id=BOE-A-2015-11596>
- AEAT — Distinción sociedad civil / comunidad de bienes: <https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/sociedades-civiles-impuesto-sobre-sociedades/que-son-sociedades-civiles/distincion-sociedad-civil-comunidad-bienes.html>
