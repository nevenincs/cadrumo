---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
  - "[[2026-05-21-persona-fleet-round3-findings-audit]]"
---

# `cli-workflow-redesign` research: grounding the three-axis taxpayer model

This is the research phase (Implementation step 1) of
`2026-05-21-taxpayer-type-applicability-adr`. The ADR accepts the
direction — the profile gains a structured three-axis taxpayer model
(entity type, tax regime, special enrolments) and modelos / calendar /
calculations / brackets / special rules derive from it — but mandates
that no schema or engine change land before its rules are grounded in
BOE / AEAT authority. This document supplies that grounding and maps
the gap against the current codebase.

The defect the ADR closes: the `overview` applicability engine
hard-codes an `AutonomoProfile` and so reports **Modelo 130
applicable and overdue** for the landlord persona Bernat
(`2026-05-21-persona-fleet-round3-findings-audit` Q1) whose only income
is *rendimientos del capital inmobiliario*.

## Scope and honesty boundary

Every regulatory claim below carries a source. The AEAT website
(`sede.agenciatributaria.gob.es`, `agenciatributaria.es`) and the BOE
(`boe.es`) were consulted directly. Where a fact could not be
confirmed from an authoritative page within the research budget, it is
flagged explicitly in the **Limits of grounding** section rather than
asserted. The registry track must verify every encoded rule against
the cited BOE article text before it ships — this document grounds
the *direction and shape*, not the final per-casilla legal text.

---

## Axis 1 — Entity type

Entity type is the most consequential axis: it selects the *tax*
(IRPF vs Impuesto sobre Sociedades vs régimen de atribución), and the
tax selects the modelos, the calendar, and the rate schedule wholesale.

### 1.1 Natural person (persona física)

A natural person resident in Spain is an IRPF taxpayer (contribuyente
del IRPF, Ley 35/2006 LIRPF, BOE-A-2006-20764). The annual
self-assessment is **Modelo 100** (declaración de la Renta). What
matters for applicability is *which IRPF income categories
(rendimientos)* the person has, because the quarterly/informational
modelo obligations derive from the category, not from being a natural
person as such:

- **Rendimientos de actividades económicas** (autónomo / empresario
  individual / profesional) — LIRPF Arts. 27-32. This is the *only*
  category that triggers the quarterly pago fraccionado
  **Modelo 130** (estimación directa) or **Modelo 131** (estimación
  objetiva). Source: AEAT Modelo 130 procedure G601
  (`sede.agenciatributaria.gob.es/Sede/procedimientos/G601.shtml`)
  states M130 is for "contribuyentes que ejercen actividades
  económicas... método de estimación directa". The current engine's
  autónomo-default is *correct only for this category*.
- **Rendimientos del trabajo** (employment / pensions) — LIRPF
  Arts. 17-20. A salaried-only taxpayer or a pensioner has **no
  Modelo 130 obligation** and typically no quarterly filings at all;
  withholding is operated by the payer (Modelo 111 is the *payer's*
  obligation, not the employee's). Pensions are rendimientos del
  trabajo for IRPF purposes (LIRPF Art. 17.2.a).
- **Rendimientos del capital inmobiliario** (immovable property /
  rental income) — LIRPF Arts. 22-24. This is Bernat's category. A
  pure landlord declares rental income annually on **Modelo 100** and
  has **no actividad económica and no Modelo 130** unless the rental
  rises to the level of an actividad económica under LIRPF Art. 27.2
  (the "persona empleada con contrato laboral y a jornada completa"
  test). This is the exact mis-classification the ADR fixes.
- **Rendimientos del capital mobiliario** (movable capital:
  dividends, interest) — LIRPF Arts. 25-26. Declared on Modelo 100;
  withholding operated by the payer.
- **Ganancias y pérdidas patrimoniales** (capital gains) — LIRPF
  Arts. 33-39. Declared on Modelo 100.

The practical consequence for the engine: a natural person whose
declared income categories do **not** include *actividades
económicas* must not be offered Modelo 130/131, Modelo 303 (IVA),
Modelo 111/115 payer obligations, or Modelo 347 as applicable. The
category set, not "is a natural person", is the gate.

> Note: the project already models the *individual vs joint* Renta
> declaration split as `RentaDeclaracionType` (see
> `src/aeat/domain/profile/_renta_codes.py`, consumed by
> `SetupAnswers.taxation_type`). That is the Modelo 100 *declaration
> mode*, not the entity type or income category — it is orthogonal to
> this axis and must not be conflated with it.

### 1.2 Legal entities — Impuesto sobre Sociedades

A legal entity with personalidad jurídica is generally a contribuyente
del Impuesto sobre Sociedades (IS), Ley 27/2014 LIS
(BOE-A-2014-12328). It does **not** file Modelo 100. The recognised
common forms:

- **Sociedad de responsabilidad limitada (S.L. / S.R.L.)** — the
  default SME company form.
- **Sociedad anónima (S.A.)**.
- **Sociedad cooperativa** — taxed under IS but with a reduced rate;
  fiscally-protected cooperatives carry a -3 percentage-point
  reduction on the general rate (LIS Art. 29, confirmed in the
  project registry `legal/is.toml` `ley-27-2014:art-29` notes).
- **Sociedad civil con personalidad jurídica y objeto mercantil** —
  since 2016 these are IS contribuyentes, *not* atribución de rentas.
  Source: AEAT "Distinción entre sociedad civil y comunidad de
  bienes"
  (`sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/sociedades-civiles-impuesto-sobre-sociedades/que-son-sociedades-civiles/distincion-sociedad-civil-comunidad-bienes.html`):
  "el único contribuyente que se incorpora al Impuesto sobre
  Sociedades [son] las sociedades civiles con personalidad jurídica y
  objeto mercantil".
- **Asociaciones / fundaciones / entidades sin fines lucrativos** —
  IS contribuyentes, partially exempt; entidades sin fines lucrativos
  acogidas a Ley 49/2002 pay a reduced 10% rate (LIS Art. 29).

IS taxpayer modelos and calendar:

- **Modelo 200** — annual IS self-assessment. Applies, in general, to
  *all* IS contribuyentes (and IRNR permanent establishments).
  Deadline: **25 calendar days following the 6 months after the end
  of the tax period** — for a calendar-year entity, **1-25 July** of
  the following year. Source: LIS Art. 124 (registry `legal/is.toml`
  `ley-27-2014:art-124`: "25 días naturales siguientes a los 6 meses
  posteriores a la conclusión del período impositivo"); AEAT "Plazos
  de presentación"
  (`sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/gestion-impuesto-sobre-sociedades/plazos-presentacion.html`).
  The project already carries this window for the 2024 exercise in
  `registry/aeat/modelos/200/.../deadline_windows.toml`
  (`opens_on = 2025-07-01`, `closes_on = 2025-07-25`).
- **Modelo 202** — IS pago fraccionado. Three instalments per year,
  filed in the **first 20 calendar days of April, October and
  December** (1/15-day window when direct-debited). Source: LIS
  Art. 40 (registry `legal/is.toml` `ley-27-2014:art-40`: "20 días
  naturales de los meses de abril, octubre y diciembre"); AEAT
  Modelo 202 instructions
  (`sede.agenciatributaria.gob.es/.../modelo-202-is-...`/instrucciones).
  Two modalidades: cuota-íntegra method (LIS Art. 40.2) and
  base-imponible method (LIS Art. 40.3). The base-imponible method is
  **mandatory** for entities whose importe neto de la cifra de
  negocios (INCN) exceeded a threshold in the prior 12 months — the
  commonly-cited threshold is **6 million euros**; the exact figure
  and reference (LIS Art. 40.3) must be confirmed against the BOE
  article text by the registry track (flagged in Limits).
- **Modelo 220** — annual IS declaration for fiscal-consolidation
  groups (régimen de consolidación fiscal, LIS Title VII Chapter VI).
  Filed by the sociedad dominante / entidad representativa. Deadline:
  the deadline of the representative entity's individual Modelo 200
  (LIS Art. 82). Source: AEAT Modelo 220 procedure GE02
  (`sede.agenciatributaria.gob.es/Sede/procedimientos/GE02.shtml`).
  Each group member still files its own theoretical Modelo 200
  (LIS Art. 56.3).
- **Modelo 222** — pago fraccionado for fiscal-consolidation groups
  (parallels Modelo 202). Approved together with Modelo 202 by Orden
  HFP/227/2017 (BOE-A-2017-2778).

IS rate schedule (LIS Art. 29, grounded in registry `legal/is.toml`):
25% general; micro-empresa scale 17% (0-50.000) / 20% (rest);
fiscally-protected cooperatives -3 pp; entidades sin fines lucrativos
10%; newly-created entities 15% for the first two profit-making
periods; credit/hydrocarbon entities 30%. This is an **entirely
different rate schedule from the IRPF brackets** — a company never
uses the IRPF tarifa.

The concrete contrast the ADR demands the engine express: an
**autónomo files Modelo 100 (Renta) + Modelo 130 + Modelo 303**; an
**S.L. files Modelo 200 + Modelo 202 (+ 220/222 if a group), and
never Modelo 100 or Modelo 130** — different modelos, different
calendar (July annual vs the Renta April-June campaign; April/Oct/Dec
fraccionados vs the IRPF quarterly), different rates.

### 1.3 Entities without legal personality — régimen de atribución de rentas

**Comunidades de bienes (CB)**, **sociedades civiles sin objeto
mercantil**, herencias yacentes, and any entity lacking personalidad
jurídica that forms a unidad económica are **not IS or IRPF
taxpayers in their own right**. They fall under the *régimen de
atribución de rentas* (LIRPF Title X Section 2): the income is
attributed to and taxed in the hands of each socio / comunero /
partícipe according to that member's own tax (IRPF, IS, or IRNR).
Source: AEAT "Entidades en régimen de atribución de rentas"
(`sede.agenciatributaria.gob.es/Sede/irpf/empresarios-individuales-profesionales/entidades-regimen-atribucion-renta.html`)
and "Distinción sociedad civil / comunidad de bienes" (above). The
attributed income "tendrá la naturaleza derivada de la actividad o
fuente de donde proceda".

These entities have their own informational obligation (Modelo 184)
but the *substantive* tax filing is each member's. The project
registry already references atribución de rentas
(`registry/aeat/legal/atribucion-rentas.toml`, and Modelo 200 casilla
`0053-entidad-en-regimen-de-atribucion-de-rentas-con-tri`). For the
taxpayer-model axis this means the entity-type enum needs a third
branch beyond "natural person" and "IS legal entity": an
**attribution entity** whose filing profile is derived from the
members, not from the entity.

---

## Axis 2 — Tax regime

### 2.1 IRPF estimation regimes (for actividades económicas)

For a natural person with *rendimientos de actividades económicas*,
the method of determining net income is a closed regime choice
(LIRPF Arts. 16, 28-31; RIRPF RD 439/2007 Arts. 30-31, already cited
as the `irpf-regime` topic `legal_refs`):

- **Estimación directa normal (EDN)** — full accounting; the default
  for activities not eligible for or excluded from the other regimes.
  Pago fraccionado on **Modelo 130**.
- **Estimación directa simplificada (EDS)** — applies when the INCN
  of all activities did not exceed **600.000 €** in the prior year
  and the taxpayer has not renounced it. Source: AEAT "Estimación
  directa simplificada"
  (`sede.agenciatributaria.gob.es/Sede/irpf/empresarios-individuales-profesionales/regimenes-determinar-rendimiento-actividad/estimacion-directa-simplificada.html`).
  Simplified deductible-expense rules (notably a 5% gastos de difícil
  justificación deduction, capped — cap figure to be confirmed by the
  registry track). Pago fraccionado also on **Modelo 130**.
- **Estimación objetiva (EO / módulos)** — net income computed from
  signos, índices y módulos rather than real income/expense, for
  activities and thresholds listed in the annual Orden de Módulos
  (the project already references `Orden HAC/1425/2025` in the
  profile schema for the transport withholding carve-out). Pago
  fraccionado on **Modelo 131**, not 130. Source: AEAT Modelo 131
  procedure G602 and "Los módulos en el IRPF"
  (`sede.agenciatributaria.gob.es/Sede/empresarios-individuales-profesionales/contribuyentes-modulos/modulos-irpf.html`).

Consequence for the engine: the IRPF regime selects **Modelo 130 vs
Modelo 131**, changes the deductible-expense computation, and changes
the calculation the modelo runs. The current schema already has a
flat boolean `uses_objective_estimation` (selector
`uses_objective_estimation_irpf`) — it captures the EO branch but
collapses EDN and EDS into a single "not objective" state, losing the
EDN/EDS distinction.

### 2.2 IVA regimes

The IVA regime is a separate closed choice (Ley 37/1992 LIVA;
Art. 120 LIVA already cited as the `iva-regime` topic `legal_ref`):

- **Régimen general** — standard input/output IVA, Modelo 303
  quarterly (or monthly), Modelo 390 annual summary.
- **Régimen simplificado** — module-based IVA, coordinated with IRPF
  estimación objetiva; Modelo 303 with the simplified computation.
- **Recargo de equivalencia** — mandatory for retail traders
  (comerciantes minoristas) who are natural persons or attribution
  entities; the supplier charges an extra recargo and the retailer
  does **not** file periodic IVA self-assessments for the retail
  activity. The project already encodes the recargo bands in
  `registry/aeat/legal/iva-recargo-equivalencia.toml`.
- **Régimen especial de la agricultura, ganadería y pesca (REAGP)** —
  the farmer charges no IVA and receives a compensation (12% agrícola
  / forestal, 10,5% ganadera / pesquera). Source: AEAT REAGP manual
  (`sede.agenciatributaria.gob.es/.../regimen-especial-agricultura-ganaderia-pesca/...`).
  Commercial companies, cooperatives and SATs are **excluded** from
  REAGP — it interacts with the entity-type axis.

The current schema's `iva.regime` enum is
`["GENERAL", "SIMPLIFICADO", "RECARGO_EQUIVALENCIA", "EXENTO"]` and
the domain `IVARegime` enum mirrors it. It is **missing REAGP** and
collapses several distinctions (e.g. EXENTO covers any
fully-exempt activity without distinguishing the basis). The IVA
regime changes which periodic modelo applies, the periodicity, and
whether Modelo 390 is owed.

---

## Axis 3 — Special enrolments, with focus on SII

Special enrolments are opt-in or threshold-triggered census states
that re-shape the modelo and ledger obligations independently of
entity type and regime. The schema already models some
(`iva.roi_enrolled` for ROI/VIES, `iva.oss_enrolled` for OSS/IOSS,
`large_company`, `public_administration_budget_gt_6000000`). The ADR
flags **SII** as the axis the project owner could not ground himself.

### 3.1 SII — Suministro Inmediato de Información

The SII is the AEAT system for electronically supplying the IVA
*Libros registro* (invoicing record books) in near-real time through
the Sede electrónica, replacing the old book-keeping + summary-return
model.

**Legal basis.** The SII was created by **Real Decreto 596/2016, de 2
de diciembre** (modifying the Reglamento del IVA RD 1624/1992), with
technical specifications in **Orden HFP/417/2017, de 12 de mayo**
(BOE-A-2017-5312, BOE núm. 115, 15 May 2017). It has applied **since
1 July 2017**; RD 596/2016's transitional provision required the
first-semester-2017 records to be supplied between 1 July and 31
December 2017. Sources: BOE-A-2017-5312
(`boe.es/buscar/act.php?id=BOE-A-2017-5312`); AEAT SII boletín
informativo
(`sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G417/FicherosSuministros/bolinform_SII_es_es.pdf`);
AEAT "Información general"
(`sede.agenciatributaria.gob.es/Sede/iva/suministro-inmediato-informacion/informacion-general.html`).
The project's `topics/sii-verifactu.toml` already lists `rd-596-2016`
and `rd-1007-2023` as `legal_refs` but these are topic-level slugs,
not the BOE-keyed legal entries the calculation-grounding rule
requires — see the gap section.

**Who is obliged.** The mandatory SII collective is every sujeto
pasivo whose IVA self-assessment period is **monthly**, namely:

- **Grandes empresas** — turnover above 6.010.121,04 € in the prior
  year (the "gran empresa" threshold; AEAT phrases it as "facturación
  superior a 6 millones de €").
- Taxpayers registered in **REDEME** (Registro de Devolución Mensual
  del IVA).
- **Grupos de IVA** (régimen especial del grupo de entidades).
- Fuel/warehouse depot operators (extended to this collective from
  01/01/2025).

Source: AEAT "Información general" and "Nuevo sistema de gestión del
IVA"
(`sede.agenciatributaria.gob.es/Sede/impuestos-tasas/iva/iva-libros-registro-iva-traves-aeat/nuevo-sistema.html`).

**Who can opt in.** Any other sujeto pasivo may **voluntarily** opt
into the SII (via the Modelo 036 census). A voluntary entrant keeps
its quarterly settlement period but must remain in the SII for at
least the calendar year. Source: AEAT "Información general".

**What it changes — ledger submission.** Under the SII, the four
Libros registro del IVA (facturas expedidas, facturas recibidas,
bienes de inversión, determinadas operaciones intracomunitarias) are
kept *at the AEAT Sede* by sending the invoice detail electronically
(XML web-service messages or a web form) within **four days**
(business days, excluding Saturdays, Sundays and national holidays)
of issuing/recording the invoice. Source: AEAT "Información general"
("plazo de cuatro días").

**What it changes — modelo obligations.** SII participants are
exempt from:

- **Modelo 347** — declaración anual de operaciones con terceras
  personas; and
- **Modelo 390** — declaración-resumen anual del IVA.

The Modelo 390 suppression for SII filers is in Orden
HFP/417/2017. Source: AEAT "Nuevo sistema de gestión del IVA"
("no están obligados a presentar... el modelo 347... y... el modelo
390"). SII filers still file periodic **Modelo 303** (monthly for the
mandatory collective).

**Engine consequence.** SII enrolment must (a) suppress Modelo 347
and Modelo 390 from the applicability set, (b) for the mandatory
collective, switch Modelo 303 periodicity from quarterly to monthly,
and (c) drive the near-real-time ledger-submission obligation, which
is a *new obligation class* the deadline engine does not model today
(it only models periodic modelo windows). Because SII introduces a
genuinely new obligation type and interacts with REDEME / grupos /
gran-empresa, it warrants a **child ADR** (see Wave plan).

### 3.2 Related: VERI*FACTU

`topics/sii-verifactu.toml` couples SII with VERI*FACTU
(RD 1007/2023, anti-fraud invoicing software / "sistemas
informáticos de facturación"). VERI*FACTU is a *distinct* regime
from the SII — it concerns the certification and optional real-time
reporting of invoicing *software*, not the IVA Libros registro. The
two should not be merged into one enrolment flag. VERI*FACTU's
applicability timeline and obligated population were **not fully
grounded in this research pass** — flagged in Limits.

### 3.3 Other enrolments already partly modelled

- **ROI / VIES** (`iva.roi_enrolled`) — Registro de Operadores
  Intracomunitarios; gates Modelo 349 and the ROI live
  cross-references. Already a schema field.
- **OSS / IOSS** (`iva.oss_enrolled`) — one-stop-shop for intra-EU
  B2C; gates Modelo 369. Already a schema field.
- **Gran empresa** (`large_company`) — already a schema field; note
  it is the *same* 6.010.121,04 € threshold that triggers mandatory
  SII, so the two facts are correlated and the derivation engine
  should treat gran-empresa as implying mandatory SII unless an
  explicit SII enrolment fact says otherwise.
- **REDEME** — **not modelled today**; needed because it is one of
  the mandatory-SII triggers.

---

## Current codebase state and the precise gap

### 4.1 What the profile schema captures today

`src/aeat/_data/registry/aeat/user_profile/schema.toml` (schema
version 1) has these axis-relevant fields, all *flat*:

- `activities` (repeatable: `description` free text, `cnae`,
  `iae_epigraph`) — describes *what* the activity is but carries **no
  entity-type and no income-category** classification.
- `iva.regime` enum — `GENERAL | SIMPLIFICADO | RECARGO_EQUIVALENCIA
  | EXENTO` (required). Partial Axis-2 coverage; **missing REAGP**.
- `irpf.uses_objective_estimation` boolean (selector
  `uses_objective_estimation_irpf`) — a single boolean that captures
  EO but **collapses EDN vs EDS**.
- `census.status` (`alta | modificacion | baja`),
  `census.large_company`, `census.public_administration_budget_...`,
  `census.activity_start_date` / `activity_end_date`,
  `census.establecimiento_type`, `census.elected_withholding_pct`.
- `iva.does_intracomunitario`, `iva.roi_enrolled`, `iva.oss_enrolled`,
  `iva.intracommunity_operations_exceed_50000_eur`.
- Withholding-payer booleans (`has_employees`,
  `pays_professionals_with_retencion`, `pays_rent_with_retencion`,
  `pays_capital_income_with_retencion`).
- `obligations.third_party_transactions_above_347_threshold`,
  `obligations.bienes_extranjero_above_threshold`.
- `renta_taxpayer` / `renta_spouse` / `renta_family` /
  `properties` — Modelo 100 person data, including `properties.use_type`
  (`habitual | rental | mixed | imputed_income | other`).
- `filing_export.declaration_type` — free-text string (the
  individual/joint Renta mode is carried via `SetupAnswers.taxation_type`
  as `RentaDeclaracionType`, not in the schema enum).

There is **no `entity_type` field, no income-category set, no
estimation-regime enum, and no SII / REDEME enrolment field.**

### 4.2 What the applicability engine does today

- The domain model is `AutonomoProfile`
  (`src/aeat/domain/deadlines/_models.py`) — the *name itself* hard-
  codes the autónomo assumption. Its fields are exactly the flat
  schema booleans above plus `iva_regime: IVARegime`. There is no
  field for entity type or income category.
- `autonomo_profile_from_mapping`
  (`src/aeat/domain/deadlines/_profiles.py`) projects a profile-values
  mapping into an `AutonomoProfile`, padding identity defaults so a
  "schedule-only" empty profile still validates — i.e. an undeclared
  profile silently becomes a valid autónomo.
- `DeadlineEngine` (`src/aeat/domain/deadlines/_engine.py`) computes
  the schedule purely from registry `deadline_windows` +
  `filing_schedules` + `applicability_conditions`
  (`ProfilePredicateDefinition`) evaluated against the
  `AutonomoProfile`. Applicability is therefore *already*
  registry-condition-driven — but every condition is written against
  autónomo-shaped fields, and there is no condition that can express
  "this modelo only applies to an IS contribuyente" or "only to a
  taxpayer with actividad económica" because **the profile carries no
  such fact to test**.
- `build_overview_explain` / `build_overview_calendar` /
  `build_overview_agenda` (`src/aeat/application/overview/`) all take
  an `AutonomoProfile` and surface `applies_to` / `explain`. The
  calendar's `_GATING_FIELDS` warning table covers `iva.regime`,
  `does_intracomunitario`, `pays_professionals_with_retencion`,
  `pays_rent_with_retencion`, `uses_objective_estimation_irpf` — it
  warns when these are *unset*, but it has **no concept of "the
  taxpayer model itself is undeclared"** and so never refuses to
  answer; it just computes the autónomo default.

### 4.3 The precise gap

1. **No entity-type axis at all.** The profile cannot say "this is
   an S.L." or "this is a comunidad de bienes". Every profile is an
   autónomo. There is no way to route to Modelo 200/202 or to
   suppress Modelo 100/130.
2. **No income-category axis for natural persons.** A natural person
   cannot declare "rental income only, no actividad económica"
   (Bernat's case) or "employment only" or "pension only". So
   Modelo 130/303/347 cannot be gated out for non-activity natural
   persons — the round-3 Q1 defect.
3. **Regime axis is lossy.** EDN vs EDS is collapsed into one boolean;
   the IVA regime enum is missing REAGP.
4. **SII / REDEME enrolments absent.** No field can express SII
   enrolment, so Modelo 390/347 suppression and monthly-303 switching
   cannot be derived; the near-real-time ledger obligation is not
   modelled as an obligation class at all.
5. **Engine has no "incomplete" answer.** The ADR's "default must be
   safe" constraint is unmet: with the taxpayer model undeclared the
   engine confidently returns the autónomo schedule rather than an
   honest "declare your taxpayer type first".
6. **The IS rate / IRPF bracket selection is not derived.** The IS
   registry grounding (`legal/is.toml`, Modelo 200/202 revisions)
   already exists, but nothing routes a profile *to* the IS rate
   schedule vs the IRPF tarifa — because there is no entity-type
   fact to route on.
7. **Naming debt.** `AutonomoProfile`, `autonomo_profile_from_mapping`,
   and the `topics`/registry "autónomo"-shaped vocabulary bake the
   defaulted assumption into identifiers. Per the source-hygiene rule
   the renamed model should carry an entity-neutral name (e.g.
   `TaxpayerProfile`).

### 4.4 What already exists and can be reused

- **IS registry grounding is substantial.** `legal/is.toml` carries
  reviewed BOE-keyed entries for LIS Arts. 29 (rates), 30 (cuota),
  40 (pago fraccionado), 124 (declaration deadline), 82-ref material,
  plus Modelo 200 (`revisions/2024-y-siguientes`) and Modelo 202
  (`revisions/2025-y-siguientes`, `2023-2024`, `2019-2022`) with
  casillas, export layouts, and the Modelo 200 deadline window. The
  corporate calculation model has registry foundations to build on.
- **Régimen de atribución** is partly grounded
  (`legal/atribucion-rentas.toml`, Modelo 200 casilla 0053).
- **The applicability engine is already registry-condition-driven**
  (`ProfilePredicateDefinition` / `evaluate_profile_conditions`) — the
  derivation rewrite extends the *fact set the conditions can test*,
  it does not need a new evaluation mechanism.
- **Enrolment fields** `roi_enrolled` / `oss_enrolled` /
  `large_company` show the pattern for the new SII / REDEME fields.

---

## Proposed wave slicing and child-ADR recommendations

The ADR's Implementation section already names five steps
(Research / Schema / Derivation engine / Registry rules / Child ADRs).
The slicing below refines them into an executable wave order; it is a
proposal for the plan author, not a binding plan.

### Wave 1 — Schema: the three-axis taxpayer model

Add to the profile schema (a schema-version bump) and the domain
model:

- `entity_type` enum — `natural_person | is_legal_entity |
  attribution_entity` (the three branches grounded in Axis 1). A
  finer `is_legal_entity` sub-form (`sl | sa | cooperativa |
  sociedad_civil_mercantil | sin_fines_lucrativos | other`) can be a
  nested field where the rate schedule needs it.
- For `natural_person`: an income-category set —
  `actividad_economica | trabajo | capital_inmobiliario |
  capital_mobiliario | ganancias_patrimoniales | pension` — closed,
  multi-select. This is the field a pure landlord sets to exclude
  Modelo 130.
- `irpf_estimation_regime` enum — `directa_normal |
  directa_simplificada | objetiva` — replacing the lossy
  `uses_objective_estimation` boolean.
- Extend `iva.regime` with `REAGP`.
- New enrolment fields: `sii_enrolled`, `redeme_enrolled` (and
  consider keeping VERI*FACTU separate per Axis 3.2).

Rename `AutonomoProfile` to an entity-neutral name. Wizard collects
the new fields in plain operator language. This wave ships with strict
roundtrip tests per the persistence-boundary rule.

### Wave 2 — Derivation engine and the safe default

Rewrite `build_overview_explain` / `_calendar` / `_agenda` and the
`DeadlineEngine` consumption so applicability, the calendar,
calculation selection, and bracket resolution **derive** from the
taxpayer model through registry conditions. Remove the autónomo
default; an undeclared taxpayer model yields an explicit
"incomplete" answer rather than a confident wrong one. Extend
`ProfilePredicateDefinition` conditions so registry rules can test
`entity_type`, the income-category set, and the regime.

### Wave 3 — Registry rules and the missing deadline windows

Populate per-entity / per-regime applicability and calendar data,
each with `legal_refs`. This wave also closes round-3 finding **R1**
(no registry deadline windows for Modelo 100 / 303 / 347 in 2025-2026
— the Renta window is registered nowhere) and the H6 graceful-
degradation half. SII rules (Modelo 390/347 suppression, monthly-303
switch) land here once the SII child ADR is accepted.

### Child ADR — corporate-entity calculation model

**Recommended.** Modelo 200 carries an entirely different calculation
chain (resultado contable → ajustes → base imponible → tipo de
gravamen LIS Art. 29 → cuota), a different rate schedule, and Modelo
202's two pago-fraccionado modalidades (LIS Art. 40.2 vs 40.3 with
the INCN-threshold mandatory rule). The registry grounding exists
(`legal/is.toml`, Modelo 200/202 revisions) but wiring a profile to
the IS calculation path — and deciding how `attribution_entity`
profiles are handled (member pass-through) — is a substantial
adjudication that should not be buried inside the Wave-2 engine
rewrite. This child ADR owns the IS rate schedule and the corporate
calculation routing.

### Child ADR — the SII / digital-IVA-ledger model

**Recommended.** SII introduces a *new obligation class* (near-real-
time ledger submission within four business days) that the deadline
engine — which today models only periodic modelo windows — cannot
express. It also re-shapes existing modelos (390/347 suppression,
303 periodicity) and interacts with three correlated facts
(gran-empresa, REDEME, grupos de IVA). The interaction with VERI*FACTU
(which must stay a separate regime) and the unresolved VERI*FACTU
timeline (see Limits) make this its own adjudication. This child ADR
owns the SII enrolment model and the ledger-submission obligation
class.

A finer enrolment axis (recargo de equivalencia rate effects,
OSS/IOSS Modelo 369) likely does **not** need its own ADR — it fits
the existing flag pattern and Wave-1/3 work.

---

## Limits of grounding — what could not be authoritatively confirmed

Per the safety-legal-gates and calculation-grounding rules, these
points were **not** confirmed to BOE-article precision in this
research pass and must be verified by the registry track before any
rule is encoded:

1. **Modelo 202 base-imponible mandatory threshold.** The
   base-imponible pago-fraccionado method (LIS Art. 40.3) is
   mandatory above an INCN threshold; the commonly-cited figure is
   6 million euros, but the AEAT deadline page consulted did not
   state it and the exact figure + the precise LIS Art. 40.3 wording
   were not read directly. Confirm against BOE-A-2014-12328 Art. 40.
2. **EDS gastos de difícil justificación cap.** Estimación directa
   simplificada allows a 5% deduction for hard-to-justify expenses
   with an annual cap; the cap amount (and any 2026 update) was not
   confirmed. Confirm against RIRPF RD 439/2007 and the LIRPF.
3. **Gran-empresa / SII turnover threshold exact figure.** AEAT
   pages phrase it as "facturación superior a 6 millones de €"; the
   precise legal figure is 6.010.121,04 € (the historical
   1.000.000.000 ESETA conversion). Both figures appear in AEAT
   materials; the registry should cite the regulation that fixes it.
4. **VERI*FACTU (RD 1007/2023) applicability timeline and obligated
   population.** Not researched in this pass beyond confirming it is
   a *distinct* regime from the SII. The SII child ADR must research
   it separately before coupling or separating the enrolment flags.
5. **Modelo 100 / 303 / 347 deadline windows (round-3 R1).** This
   research confirms *that* these windows are well-defined in AEAT
   law (the Renta campaign, the quarterly 303 windows, the February
   347 window) but did not transcribe the exact 2025/2026 dates;
   the registry track owns transcribing them with `legal_refs`.
6. **Per-entity-form IS rate detail.** LIS Art. 29's rate scale is
   grounded via the existing registry entry, but the 2026 micro-
   empresa bracket figures and any Ley de Presupuestos updates were
   not re-verified for the current year. Confirm against the
   in-force LIS text and the 2026 budget law.

Everything in Axes 1-3 above that is *not* in this list is supported
by the cited AEAT / BOE source; everything in this list is a
known open question handed forward.

## Sources

- AEAT — Impuesto sobre Sociedades, plazos de presentación: <https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/gestion-impuesto-sobre-sociedades/plazos-presentacion.html>
- AEAT — Modelo 200, gestión: <https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GE04.shtml>
- AEAT — Modelo 202, plazo de presentación de los pagos fraccionados: <https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/pagos-fraccionados-impuesto-sobre-sociedades/plazo-presentacion-pagos-fraccionados.html>
- AEAT — Modelo 220, régimen de consolidación fiscal: <https://sede.agenciatributaria.gob.es/Sede/procedimientos/GE02.shtml>
- AEAT — Modelo 130, IRPF estimación directa: <https://sede.agenciatributaria.gob.es/Sede/procedimientos/G601.shtml>
- AEAT — Modelo 131, IRPF estimación objetiva: <https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G602.shtml>
- AEAT — Estimación directa simplificada: <https://sede.agenciatributaria.gob.es/Sede/irpf/empresarios-individuales-profesionales/regimenes-determinar-rendimiento-actividad/estimacion-directa-simplificada.html>
- AEAT — Los módulos en el IRPF (estimación objetiva): <https://sede.agenciatributaria.gob.es/Sede/empresarios-individuales-profesionales/contribuyentes-modulos/modulos-irpf.html>
- AEAT — SII, información general: <https://sede.agenciatributaria.gob.es/Sede/iva/suministro-inmediato-informacion/informacion-general.html>
- AEAT — Nuevo sistema de gestión del IVA (SII): <https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/iva/iva-libros-registro-iva-traves-aeat/nuevo-sistema.html>
- AEAT — SII boletín informativo (RD 596/2016): <https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G417/FicherosSuministros/bolinform_SII_es_es.pdf>
- BOE — Orden HFP/417/2017 (SII especificaciones técnicas): <https://www.boe.es/buscar/act.php?id=BOE-A-2017-5312>
- BOE — Orden HFP/227/2017 (modelos 202 y 222): <https://www.boe.es/buscar/doc.php?id=BOE-A-2017-2778>
- BOE — Orden EHA/672/2007 (modelos 130 y 131): <https://www.boe.es/buscar/act.php?id=BOE-A-2007-6032>
- AEAT — Régimen especial de la agricultura, ganadería y pesca: <https://sede.agenciatributaria.gob.es/Sede/iva/regimenes-tributacion-iva/regimen-especial-agricultura-ganaderia-pesca/que-consiste-regimen-especial-agricultura-pesca.html>
- AEAT — Entidades en régimen de atribución de rentas: <https://sede.agenciatributaria.gob.es/Sede/irpf/empresarios-individuales-profesionales/entidades-regimen-atribucion-renta.html>
- AEAT — Distinción sociedad civil / comunidad de bienes: <https://sede.agenciatributaria.gob.es/Sede/impuesto-sobre-sociedades/sociedades-civiles-impuesto-sobre-sociedades/que-son-sociedades-civiles/distincion-sociedad-civil-comunidad-bienes.html>
- BOE — Ley 27/2014 LIS (corpus, registry `legal/is.toml`): BOE-A-2014-12328
- BOE — Ley 35/2006 LIRPF: BOE-A-2006-20764
