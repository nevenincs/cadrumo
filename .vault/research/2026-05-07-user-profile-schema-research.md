---
tags:
  - '#research'
  - '#user-profile-schema'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-user-profile-registry-dependencies-reference]]"
  - "[[2026-05-07-user-profile-filing-export-dependencies-reference]]"
  - "[[2026-05-07-user-profile-deadline-dependencies-reference]]"
  - "[[2026-05-07-user-profile-renta-dependencies-reference]]"
  - "[[2026-05-07-user-profile-census-business-dependencies-reference]]"
---



# `user-profile-schema` research: `Modelo Driven User Profile Schema`

Topic: centralized, schema-driven user profile definition derived from modelo
calculation, filing, schedule, census, Renta, inmueble, IVA, and category
requirements.

Audit surface: current profile read/write surfaces, setup flow, secure-object
persistence, registry profile selectors, filing/export headers, deadline
calendar predicates, Modelo 100 personal/family/tax-residence bindings, rental
domain records, category usage ratios, VAT classification, Modelo 036 corpus,
and official census/Renta grounding.

Rewrite scope: this research prepares the ADR for a clean reimplementation. It
does not preserve legacy runtime profile APIs, alias maps, migration bridges,
stub layers, or deferred compatibility layers. Existing profile roots are
replacement targets.

## Findings

### The profile shape is modelo-driven, not setup-driven

The required user profile is the factual substrate the registry needs to decide
filing obligations, calculation inputs, export headers, schedule cadence,
casilla filtering, and model/revision preflight. The current setup flow captures
only a partial business profile and cannot be the authority for the schema
shape.

The codebase currently has multiple profile roots: scalar `PROFILE_KEYS`,
deadline `AutonomoProfile`, `TaxResidenceProfile`, `RentaFamilyProfile`,
untyped `UserCliState.profiles`, separate usage-ratio secure objects, and
separate setup secure-object profiles. These surfaces overlap but do not share
one schema, one validation contract, or one read/write API.

Evidence anchors: `src/aeat/domain/profile/_keys.py:108`,
`src/aeat/application/profile/__init__.py:75`,
`src/aeat/domain/deadlines/_models.py:86`,
`src/aeat/application/user_cli.py:62`,
`src/aeat/application/setup/_env_writer.py:140`,
`src/aeat/domain/usage_ratios/_service.py:27`.

### TOML must define schema and validation; secure DB must store live values

The centralized profile needs an explicit TOML schema definition for fields,
sections, types, required/conditional rules, effective-date semantics, registry
selector mappings, and model/revision requirements. The TOML must not store
operator live values.

Live profile values and immutable filing/export snapshots must be stored in
the secure DB backend. `SecureObjectRepository` already encrypts payloads,
hashes natural lookup keys, and gates reads by sensitivity class and schema
version. The secure-persistence direction already makes secure SQL objects the
active backend for governed sensitive data.

Evidence anchors: `src/aeat/adapters/persistence/storage/sql/secure_objects.py:20`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:67`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:91`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:190`,
`src/aeat/adapters/persistence/storage/sql/_orm.py:121`, and the related
secure-persistence enforcement research and ADR.

### Canonical schema sections

The minimum schema surface derived from current modelo dependencies is:

| Section | Required scope |
|---|---|
| `identity` | NIF/NIE/CIF, person/entity type, display/legal name, surname/name split, commercial name. |
| `contact/address` | Fiscal address, postal code, contact channels, export-required address/name variants. |
| `tax_residence/jurisdiction` | CCAA, common-regime scope, explicit unsupported foral state, residence valid-from/history. |
| `census/enrollment` | Census alta/modificacion/baja state, obligation enrollment, large-company/public-administration flags, effective periods. |
| `activities` | Repeatable activity list with CNAE, IAE section/group/epigraph, activity label, start/end dates, regime, premises, affected assets/properties. |
| `irpf/withholding` | Estimation method, professional income withholding threshold, employee/professional/rent/capital withholding payer obligations. |
| `iva` | IVA regime, recargo/simplificado/OSS/IOSS/intracommunity facts, VAT ID status, periodicity, effective periods. |
| `filing/export context` | Model/revision export headers, complementaria metadata, previous justificante metadata, IBAN/payment data, developer/export metadata, snapshot identity. |
| `renta_taxpayer/spouse/family` | Taxpayer personal fields, spouse conditional fields, non-resident/EU/EEA fields, descendant/ascendant repeated rows. |
| `properties/rental` | Finca/property data, cadastral facts, acquisition/disposal, rental contracts, tenant qualification, expenses, amortization, imputation/reduction facts. |
| `usage_ratios/deductibility` | Per-category ratio overrides, home-office/vehicle/personal-use facts, health/meal cap facts, category eligibility. |
| `provenance/effective dating` | Source, collected_at, verified_at, valid_from, valid_to, profile_snapshot_id/hash, schema version. |

### Registry validation requirements

The profile schema must become a validation input for the registry. Registry
validation must reject unknown profile selector keys, unknown profile model
names, invalid fields, invalid conditional requirements, invalid selector
formats, and predicate values that do not match declared field types.

Schedule predicates must be checked against canonical selectors before runtime.
Runtime mapping aliases and broad key normalization should be removed.

Export layouts must be checked against declared profile/export-context fields
before rendering. Generic profile validation is insufficient because required
fields vary by modelo, revision, period, and export layout.

Evidence anchors: `src/aeat/domain/calculations/registry/_schema.py:544`,
`src/aeat/domain/calculations/registry/_schema.py:658`,
`src/aeat/domain/calculations/registry/_schedules.py:71`,
`src/aeat/domain/calculations/registry/_validate.py:381`,
`src/aeat/domain/calculations/registry/_validate.py:824`,
`src/aeat/application/filing/_export.py:440`.

### Filing, review, and export need profile snapshots

Filing currently freezes `profile_tax_id` into the draft but reads other active
profile headers at export time. That creates a stale-export risk: a draft can be
approved under one identity/export context and rendered later with changed live
profile fields.

The centralized API must provide a model/revision-aware profile preflight and a
snapshot policy. The ADR should choose whether snapshots are secure-object
copies, secure-object references with hashes, or deterministic effective-dated
reconstruction with hash verification.

Evidence anchors: `src/aeat/entrypoints/cli/_declaration.py:65`,
`src/aeat/entrypoints/cli/_declaration.py:407`,
`src/aeat/application/filing/_export.py:457`,
`src/aeat/application/filing/_review.py:181`,
`src/aeat/application/filing/reconciliation/_reconcile.py:160`.

### Census and official grounding support effective-dated business facts

The Modelo 036 corpus and official census guidance ground the need for NIF,
name, census alta/modificacion/baja, obligations, activities, IAE/CNAE,
locations/premises, IVA data, withholding duties, ROI/intracommunity
registration, and regime enrollment. No typed Modelo 036/037 extractor is
currently present in `src`; M037 is marked retired/replaced by M036 in portal
metadata.

Official grounding consulted:

| Source | Profile relevance |
|---|---|
| AEAT Modelo 036 census procedure and FAQ | Census alta/modification/baja, NIF, activities, withholding obligations, and entrepreneur/professional/withholder census context. |
| BOE Real Decreto 1065/2007 | Censo de Obligados Tributarios and Censo de Empresarios, Profesionales y Retenedores content, tax domicile, NIF, census obligations, and updates. |
| BOE Orden EHA/1274/2007 | Modelo 036 approval and census declaration framing. |
| AEAT Modelo 100 personal/family guidance | Personal, family, spouse, residence, and CCAA fields for IRPF/Renta. |
| AEAT Renta WEB Open guidance | Simulator projection requirements and non-filing/non-authenticated parity boundary. |

Evidence anchors: `corpus/aeat_official/disenos_registro/modelo_036/files/`,
`src/aeat/domain/portals/_entries/portal_m037_censal_simplificada.py:1`.

### Teardown targets

Replace hardcoded `PROFILE_KEYS` with schema-loaded field definitions.

Replace `application.profile.validate_profile` with schema-driven validation
and model/revision preflight validation.

Replace `UserCliState.profiles[*].values` as an untyped profile store with a
central profile API backed by secure DB storage.

Replace separate setup `AutonomoProfile` persistence with centralized profile
write APIs.

Replace standalone tax-residence and usage-ratio profile roots with centralized
profile sections or linked secure child records under the same profile API.

Remove path-existence checks before secure-object profile loads.

Replace scalar `activity` with repeatable effective-dated activity records
including CNAE/IAE/regime/location/affectation.

Replace schedule/runtime alias maps with canonical schema selectors.

Replace ad hoc export header maps with typed export-context projection and
preflight validation.

Add Modelo 036 import/mapping support from official corpus into the centralized
schema.

## ADR Options

### Option A: Central TOML schema plus secure DB value documents

TOML declares sections, fields, selectors, validations, effective-date
semantics, model/revision requirements, and legal/registry metadata. Secure DB
stores live values and immutable snapshots keyed by profile ID and schema
version.

This best satisfies the stated requirement: explicitly schema-oriented TOML,
secure DB live values, clean replacement of fragmented profile surfaces, and a
central read/write API.

### Option B: Per-modelo selector declarations with generated central schema

Modelo TOML remains the primary selector source, and a build/validation step
derives central schema coverage from model requirements.

This reduces duplicated selector metadata but makes profile UX, CLI key
discovery, import/export, and Python profile APIs harder to reason about.

### Option C: Central Python schema with TOML registry references

Python/Pydantic owns the profile schema and TOML references paths.

This is simpler to implement quickly, but it is weaker against the requirement
that the user profile be an explicit TOML schema-oriented construct.

## Recommended ADR Direction

Adopt Option A.

Create `registry/aeat/user_profile/schema.toml` as the schema and validation
authority for profile sections, canonical keys, types, effective dating,
conditional requirements, selector projections, export context, and
model/revision required fields.

Create a central domain/application API for add, remove, edit, list/read,
duplicate, export, import, validate, and model/revision preflight. CLI keys
should be canonical section paths such as `identity.name`, `identity.email`,
`tax_residence.ccaa`, `activities.0.cnae`, or
`iva.intracommunity_operations_exceed_50000_eur`.

Store live profile values and snapshots through the secure DB backend. TOML
never stores live user data.

## Risks And Open Questions

The ADR must choose the secure storage topology: one encrypted aggregate per
profile, sensitivity-split secure child objects, or linked secure records for
high-cardinality sections such as rental properties and usage ratios.

The schema must avoid storing transaction/customer facts in the operator
profile while still supporting IVA classification.

The implementation must define how effective-dated facts are selected when a
filing period crosses a census/regime/activity change.

Import/export must distinguish user-directed portable profile exports from
internal secure DB persistence.

Foral jurisdictions must be explicit unsupported states for current common
regime flows, not silently coerced into CCAA.
