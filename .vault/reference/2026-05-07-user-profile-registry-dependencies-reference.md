---
tags:
  - '#reference'
  - '#user-profile-registry-dependencies'
date: '2026-05-07'
modified: '2026-05-07'
related: []
---



# `user-profile-registry-dependencies` reference: `User Profile Registry Dependencies`

Topic: Modelo registry and calculation surfaces that currently consume profile
facts or need centralized profile facts for validation, schedule selection,
binding, snapshotting, and casilla filtering.

Audit surface: registry schema and validation modules, schedule resolution,
Modelo 100 profile bindings, deadline applicability predicates, export identity
bindings, registry snapshots, formula traces, and existing profile-domain models.

Rewrite scope: this document records code-reference findings only. It does not
design compatibility shims. Existing fragmented profile surfaces are treated as
replacement targets for a clean centralized implementation.

## Findings

### Registry calculation already consumes profile selectors

Registry-backed calculation treats profile data as a first-class selector
source. Modelo registry TOML defines casillas, bindings, formulas, filing
schedules, deadline windows, export layouts, extraction profiles, and revision
selectors. The centralized user profile schema must become the typed input
contract for those selectors.

Current profile surfaces are split across scalar profile keys, deadline
profiles, tax-residence models, family models, and secure-object usage-ratio
profiles. The implementation should replace these with one schema contract and
explicit projections at calculation boundaries.

Evidence anchors: `src/aeat/domain/profile/_keys.py:108`,
`src/aeat/domain/deadlines/_models.py:69`,
`src/aeat/domain/profile/__init__.py:85`,
`src/aeat/domain/profile/family.py:17`,
`src/aeat/domain/usage_ratios/_service.py:27`.

### Modelo 100 binds profile facts into official output fields

Modelo 100 has explicit `source = "profile"` bindings for taxpayer identity,
tax residence, declaration type, taxpayer personal status, spouse status, and
family row data. These are schema requirements, not free-form setup prompts.

Concrete scalar selector keys include `tax.id`, `surnames`, `name`,
`declaration.type`, `taxpayer.sex`, `taxpayer.marital_status`,
`taxpayer.birth_date`, `taxpayer.disability_grade`, `taxpayer.death_date`,
`spouse.tax.id`, `spouse.surnames`, `spouse.name`, `spouse.birth_date`,
`spouse.sex`, `spouse.disability_grade`, `spouse.non_resident_irpf`,
`spouse.eu_eea_resident`, `spouse.eu_eea_country`,
`family.descendants_eu_eea_deduction`, and `family.minor_children_in_unit`.

Concrete model selectors include `TaxResidenceProfile.ccaa`,
`RentaFamilyProfile.descendants.{tax_id, display_name, birth_date,
disability_grade, death_date}`, and `RentaFamilyProfile.ascendants.{tax_id,
display_name, birth_date, disability_grade, cohabiting_descendant_count,
death_date}`.

Evidence anchors: `registry/aeat/modelos/100.toml:7671`,
`registry/aeat/modelos/100.toml:7695`,
`registry/aeat/modelos/100.toml:8019`,
`src/aeat/domain/calculations/registry/test_modelo_100_registry.py:212`.

### Schedules and deadline applicability are profile driven

Modelo 111 and 349 already use profile predicates for schedule cadence.
Modelo 111 switches quarterly/monthly based on `enrollment.large_company` and
`enrollment.public_administration_budget_gt_6000000`. Modelo 349 switches
quarterly/monthly based on `does_intracomunitario` and
`iva.intracommunity_operations_exceed_50000_eur`.

Deadline applicability also reads profile facts: Modelo 111 uses
`has_employees` and `pays_professionals_with_retencion`; Modelo 115 uses
`pays_rent_with_retencion`; Modelo 123 uses
`pays_capital_income_with_retencion`; Modelo 130 uses
`professional_income_withholding_ge_70pct`; Modelo 131 uses
`uses_objective_estimation_irpf`.

Evidence anchors: `registry/aeat/modelos/111.toml:6`,
`registry/aeat/modelos/111.toml:27`, `registry/aeat/modelos/349.toml:6`,
`registry/aeat/modelos/349.toml:345`,
`registry/aeat/modelos/111.toml:1640`,
`registry/aeat/modelos/115.toml:879`,
`registry/aeat/modelos/123.toml:1114`,
`registry/aeat/modelos/130.toml:1423`,
`registry/aeat/modelos/131.toml:5946`.

### Validation is shape-only in the critical places

`ProfilePredicateDefinition.field` validates string shape but not membership in
a declared profile schema. Runtime schedule resolution walks mappings or object
attributes and fails when the predicate is evaluated. `DataBindingDefinition`
allows `source = "profile"` but keeps selector content as a generic mapping.
Registry validation has source-specific validators for some binding sources,
but not a central validator for profile selectors.

Snapshots include profile conditions as legal/source provenance, but do not
record profile schema metadata. Formula traces record formula references and
operands, not profile fact provenance.

Evidence anchors: `src/aeat/domain/calculations/registry/_schema.py:544`,
`src/aeat/domain/calculations/registry/_schema.py:658`,
`src/aeat/domain/calculations/registry/_schedules.py:71`,
`src/aeat/domain/calculations/registry/_validate.py:381`,
`src/aeat/domain/calculations/registry/_validate.py:527`,
`src/aeat/domain/calculations/registry/_validate.py:824`,
`src/aeat/domain/calculations/registry/_snapshot.py:98`,
`src/aeat/domain/calculations/registry/_formula_runtime.py:19`.

## Requirements

The centralized profile schema must expose validated selectors for:
`identity`, `contact/address`, `tax_residence/jurisdiction`,
`census/enrollment`, `activities`, `irpf/withholding`, `iva`,
`filing/export context`, `renta_taxpayer/spouse/family`,
`properties/rental`, `usage_ratios/deductibility`, and
`provenance/effective dating`.

Registry validation must reject unknown profile selector keys, unknown profile
model names, invalid model fields, invalid selector formats, invalid
`required_when_profile_key` references, and type-incompatible predicate values.

Schedule and deadline predicate validation must check `field`, `op`, and
`value` against the profile schema before runtime.

Calculation preflight must fail when a registry selector references a profile
field that the TOML schema does not declare, when a live value is missing for
an applicable required selector, or when a profile value is not effective for
the filing period.

Casilla filtering must be derived from profile-driven registry metadata:
CCAA/residence, filing type, family rows, rental/inmueble facts,
activity/regime, IVA/census enrollment, and model/revision period.

## Risks And Open Questions

The ADR must choose whether profile selectors are declared centrally and
referenced from modelos, or declared per modelo and checked against the central
schema. Either way, there must be one validation authority.

CNAE/IAE activity and census enrollment are visible domain concerns but not yet
represented as one coherent profile input. The schema needs deliberate activity
granularity instead of a scalar `activity` string.

Existing tests and helper profiles that bypass the profile schema are teardown
targets once typed profile projections exist.
