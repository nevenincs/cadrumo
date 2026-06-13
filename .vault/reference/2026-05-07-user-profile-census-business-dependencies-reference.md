---
tags:
  - '#reference'
  - '#user-profile-census-business-dependencies'
date: '2026-05-07'
modified: '2026-05-07'
related: []
---



# `user-profile-census-business-dependencies` reference: `User Profile Census Business Dependencies`

Topic: census, business activity, IVA, IRPF, withholding, category, usage-ratio,
asset, inventory, and secure-persistence surfaces that require centralized
operator profile facts.

Audit surface: setup answers, setup persistence, user CLI profile state,
tax-residence and usage-ratio stores, Modelo 036 corpus, portal entries,
category profiles, VAT classification, and secure-object persistence.

Rewrite scope: this document records dependencies and teardown targets. It does
not preserve separate profile roots or path-oriented profile assumptions.

## Findings

### Setup captures a partial business/census profile

Setup answers include NIF, IVA regime, withholding flags, intracommunity flag,
347/720 thresholds, tax residence CCAA, and default profile path. Setup then
persists an `AutonomoProfile` as a secure object and stores tax residence
separately. CLI active profile values are stored in another secure object as
untyped strings.

Evidence anchors: `src/aeat/application/setup/_models.py:86`,
`src/aeat/application/setup/_env_writer.py:140`,
`src/aeat/application/user_cli.py:62`,
`src/aeat/adapters/persistence/profile/tax_residence.py`,
`src/aeat/domain/usage_ratios/_service.py:27`.

### Census and enrollment data must be richer than scalar activity

The central profile needs census status, effective dates, large-company state,
public-administration threshold state, ROI/intracommunity enrollment, VAT
territory establishment, permanent establishment, activity list, IAE/CNAE
classification, activity start/end dates, premises/local facts, surface area,
affected surface, and activity affectation.

Local Modelo 036 corpus contains these census anchors, but no typed Modelo
036/037 extractor was located in `src`. M037 is marked retired/replaced by M036
in portal metadata.

Evidence anchors: `corpus/aeat_official/disenos_registro/modelo_036/files/`,
`src/aeat/domain/portals/_entries/portal_m037_censal_simplificada.py:1`,
`src/aeat/domain/profile/_keys.py:108`.

### IVA and IRPF obligations need effective-dated profile facts

IVA profile facts include `iva_regime`, simplified regime, recargo
equivalencia, agriculture/farming/fishing where applicable, cash accounting,
import VAT deferral, reseller/reverse-charge status, ROI/intracommunity status,
OSS/IOSS enrollment, VAT ID status, and intracommunity threshold facts.

IRPF and withholding profile facts include `has_employees`,
`pays_professionals_with_retencion`,
`professional_income_withholding_ge_70pct`, `pays_rent_with_retencion`,
`pays_capital_income_with_retencion`, `uses_objective_estimation_irpf`, and
direct normal/simplified/objective estimation enrollment by activity and date.

Evidence anchors: `src/aeat/domain/deadlines/_profiles.py:13`,
`src/aeat/domain/vat/_classification.py:211`,
`src/aeat/domain/vat/_classification.py:723`,
`registry/aeat/vat/catalogues/2025.toml:278`,
`registry/aeat/vat/catalogues/2025.toml:301`,
`registry/aeat/legal/iva*.toml`,
`registry/aeat/legal/iae.toml:14`.

### Usage ratios are live profile facts over TOML category metadata

Category profiles are TOML-backed legal/deductibility metadata. Usage-ratio
profiles are live operator overrides already persisted through secure DB. The
central profile should generalize that pattern: schema in TOML, live values in
secure DB.

Needed facts include per-category business-use ratios, home-office total area,
affected area, effective dates, personal/business-use ratios for phone and
vehicle categories, exclusive-use asset facts, meals/pernocta variants, and
health-insurance covered-person facts.

Evidence anchors: `src/aeat/domain/categories/_registry.py:28`,
`registry/aeat/categories/profiles/2025.toml:89`,
`registry/aeat/categories/profiles/2025.toml:394`,
`src/aeat/domain/usage_ratios/_model.py:39`,
`src/aeat/domain/usage_ratios/_model.py:56`,
`src/aeat/domain/usage_ratios/_service.py:58`,
`src/aeat/domain/usage_ratios/_service.py:105`.

### Secure DB backend is already the persistence center

`SecureObjectRepository` encrypts payloads, hashes natural lookup keys, and
gates reads by sensitivity class and schema version. Current setup, CLI state,
tax residence, and usage ratios all touch secure persistence, but through
separate roots.

Evidence anchors: `src/aeat/adapters/persistence/storage/sql/secure_objects.py:20`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:67`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:91`,
`src/aeat/adapters/persistence/storage/sql/secure_objects.py:190`,
`src/aeat/adapters/persistence/storage/sql/_orm.py:121`.

## Requirements

Central profile must include `identity`, `contact/address`,
`tax_residence/jurisdiction`, `census/enrollment`, `activities`,
`irpf/withholding`, `iva`, `usage_ratios/deductibility`, and
`provenance/effective dating`.

Activity schema must cover CNAE/IAE/activity code, display label, start/end
dates, IRPF estimation regime, VAT regime, census enrollment state, premises,
affected assets/properties, and source/provenance.

IVA schema must cover operator VAT regime, recargo/simplificado/OSS/IOSS and
intracommunity enrollment where applicable, VAT ID status, exemption/not-subject
facts where profile-derived, and effective periods. Transaction/customer facts
must remain transaction data, not operator profile state.

Usage ratios must remain live secure DB values validated against TOML
category-profile eligibility and ratio bounds. Category TOML stays
legal/deductibility metadata, not operator state.

Deductibility preflight must reject ratios for ineligible categories and
require profile facts for home-office area ratios, personal-use ratios, vehicle
affectation, and property/activity links.

## Teardown Targets

Remove path-existence checks before secure-object profile loads.

Replace setup `AutonomoProfile`, CLI `ProfileRecord`, standalone tax-residence
profile storage, and standalone usage-ratio profile roots with centralized
schema-backed profile APIs and secure-object storage.

Replace untyped `dict[str, str]` profile values with typed schema projections.

Replace scalar `activity` with repeatable activities including IAE/CNAE,
regime, location, affectation, and effective dates.

Profile-scope usage ratios so overrides are associated with the selected user
profile.

Build a Modelo 036 source mapper/extractor from the local official corpus into
the centralized schema.

## Risks And Open Questions

CNAE is requested but not yet visible as a central domain object. It should be
introduced deliberately rather than mapped through generic strings.

The ADR must classify profile value sections by sensitivity and storage
topology, because identity/census data and financial usage-ratio data may not
share the same sensitivity class.

Some IVA classification facts are transaction-specific. The schema must keep
the operator profile boundary clear.
