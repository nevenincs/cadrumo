---
tags:
  - '#reference'
  - '#user-profile-renta-dependencies'
date: '2026-05-07'
modified: '2026-05-07'
related: []
---



# `user-profile-renta-dependencies` reference: `User Profile Renta Dependencies`

Topic: Modelo 100, Renta personal/family/tax-residence, CCAA, spouse, family,
inmueble, rental, extraction, and Renta WEB Open profile dependencies.

Audit surface: Modelo 100 TOML profile bindings, current Renta profile models,
rental domain models and aggregate engines, inbound borrador/declaracion
parsers, and Renta WEB Open oracle projections.

Rewrite scope: this document records profile requirements for clean
centralization. Narrow standalone tax-residence and family profile roots are
replacement targets.

## Findings

### Modelo 100 already has a profile-backed personal/family construct

Modelo 100 groups profile bindings under a `renta-personal-family` construct.
Calculation consumes bound facts through binding IDs, so the centralized schema
must produce deterministic facts for scalar and repeating-row bindings.

Evidence anchors: `registry/aeat/modelos/100.toml:5451`,
`registry/aeat/modelos/100.toml:7671`,
`src/aeat/domain/calculations/registry/_bindings.py:98`.

### Taxpayer and spouse fields are filing facts

Modelo 100 requires taxpayer identity and personal fields: `tax.id`,
`surnames`, `name`, `declaration.type`, `taxpayer.sex`,
`taxpayer.marital_status`, `taxpayer.birth_date`,
`taxpayer.disability_grade`, and `taxpayer.death_date`.

Joint filing conditionally requires spouse fields when
`declaration.type == "2"`: `spouse.tax.id`, `spouse.surnames`,
`spouse.name`, `spouse.birth_date`, and `spouse.sex`. Additional spouse status
facts include `spouse.disability_grade`, `spouse.non_resident_irpf`,
`spouse.eu_eea_resident`, and `spouse.eu_eea_country`.

Evidence anchors: `registry/aeat/modelos/100.toml:7669`,
`registry/aeat/modelos/100.toml:7705`,
`registry/aeat/modelos/100.toml:7717`,
`registry/aeat/modelos/100.toml:7729`,
`registry/aeat/modelos/100.toml:7753`,
`registry/aeat/modelos/100.toml:7837`,
`src/aeat/domain/profile/_keys.py:158`,
`src/aeat/domain/profile/_keys.py:281`.

### Tax residence is a jurisdiction selector, not an address field

Modelo 100 binds `TaxResidenceProfile.ccaa` to `ZCCAD` and
`codigoCADeclaracion`. The current CCAA model excludes foral regimes and raises
for Navarra/Pais Vasco aliases. The centralized schema should preserve the
common-regime boundary explicitly and use residence to drive autonomic casilla
filtering.

Evidence anchors: `src/aeat/domain/profile/__init__.py:48`,
`src/aeat/domain/profile/__init__.py:85`,
`registry/aeat/modelos/100.toml:7693`.

### Family rows need typed repeated collections

Scalar family facts include `family.descendants_eu_eea_deduction` and
`family.minor_children_in_unit`. Repeated descendant rows require `tax_id`,
`display_name`, `birth_date`, `disability_grade`, and `death_date`. Repeated
ascendant rows require the same core fields plus
`cohabiting_descendant_count`.

Evidence anchors: `src/aeat/domain/profile/family.py:17`,
`src/aeat/domain/profile/family.py:47`,
`src/aeat/domain/profile/family.py:82`,
`registry/aeat/modelos/100.toml:7873`,
`registry/aeat/modelos/100.toml:7897`,
`registry/aeat/modelos/100.toml:7957`.

### Inmueble and rental facts are deeper than property address

Rental domain data includes finca/property identifiers, address, cadastral
values, acquisition cost/date, disposal date, use type, stressed-area state,
contract dates, tenant qualification, public-program flags, prior/initial rent,
rehabilitation dates, LAU compliance, yearly rent received, rented days,
expenses, and amortization.

Rental aggregates compute `ingresos_integros`, `gastos_deducibles`,
`amortizacion`, `reduccion_arrendamiento_vivienda`,
`imputacion_rentas_inmobiliarias`, per-finca attribution, and per-contract
reduction-tier attribution.

Evidence anchors: `src/aeat/domain/rental/_models.py:30`,
`src/aeat/domain/rental/_models.py:94`,
`src/aeat/domain/rental/_models.py:194`,
`src/aeat/domain/rental/_aggregates.py:120`,
`src/aeat/domain/rental/_aggregates.py:412`,
`src/aeat/domain/rental/_tier_resolver.py:142`.

### Extraction and Renta WEB Open need profile projections

Inbound borrador/declaracion parsers can filter by registry extraction profile,
but Modelo 100 currently lacks extraction profile entries. Renta WEB Open uses
a separate synthetic shape: `nif`, `name`, `civil_status`, `birth_date`,
`sex`, and `autonomous_community`.

Evidence anchors: `src/aeat/adapters/inbound/borrador/_parser.py:28`,
`src/aeat/adapters/inbound/declaracion/_parser.py:312`,
`src/aeat/domain/calculations/registry/_renta_web_open_oracle.py:30`,
`src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py:181`.

## Requirements

Central profile must include `tax_residence/jurisdiction`,
`renta_taxpayer/spouse/family`, and `properties/rental` as canonical schema
sections.

Modelo 100 preflight must validate CCAA, declaration type, taxpayer personal
fields, spouse conditional requirements, family repeating rows, and
rental/inmueble completeness before casilla calculation/export.

CCAA must drive autonomic deduction filtering. Tax residence must carry
effective dating and common/foral scope, not only a postal address.

Rental profile must support effective-dated finca and contract records:
cadastral reference, use type, ownership share, habitual/non-habitual state,
rental periods, tenant facts, reduction-tier facts, expenses, amortization, and
imputation inputs.

The profile schema should provide fact-to-casilla indexes for identity/family
rows, CCAA-specific deductions, inmueble/rental sections, and generated
exportable facts.

The schema must define a Renta WEB Open projection from canonical profile
fields to AEAT simulator display values, including CCAA labels, civil-status
labels, date formatting, and sex labels.

## Risks And Open Questions

The ADR must choose whether rental records are embedded under the profile
aggregate or stored as linked secure ledgers referenced by profile IDs.

Family row data needs stable ordering and provenance so repeated XML/dictionary
outputs remain deterministic.

Extraction profiles for M100 are absent today. Casilla filtering can be added
through generated extraction-profile metadata or explicit registry entries.
