---
tags:
  - '#research'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:181be2359bb4f455250edc317e921e7c186cc48a57ebee6a30c818ec6fd1c562'
related: []
---

# `facts-registry` research: `Tax fact discovery and blast radius`

Tax and legally governed facts currently resolve through several independent
code and data paths. The risk is not only duplicated numbers: rates,
thresholds, dates, code sets, applicability classifications, and mandatory text
can each become a second authority when Python supplies the operative value and
the registry supplies only a parity check. Every inventory item below is a
candidate from static analysis, not a claim of exhaustive coverage.

## Findings

### The principal Python module is an operative legal-value store

`src/cadrumo/core/external_constants.py:531` through
`src/cadrumo/core/external_constants.py:822` declares at least 35 candidate
scalar or scheduled legal facts and four modelo classification groups.
`src/cadrumo/external_constants.toml:1` configures endpoints and paths; it does
not supply those legal values.

### Several Python values bypass data that already carries the same fact

Runtime reads the Python Modelo 347 threshold at
`src/cadrumo/application/aggregation/_counterpart.py:334`, while the revisioned
registry declares `3005.06` at
`src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/parameters/0001-threshold.toml:9`
and
`src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/parameters/0001-threshold.toml:9`.
The article 7.p cap and maritime coefficient occur in
`src/cadrumo/_data/registry/aeat/categories/trabajador_del_mar.toml:23`, but
`src/cadrumo/domain/renta/maritime_exemption.py:279` consumes Python constants.
Modelo 100 holds revisioned maternity parameters at
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0067-renta-2025-maternidad-art-81-1.toml:1`, while
`src/cadrumo/application/modelo/profile_binding.py:390` selects behavior using
a static cutoff.

### Computed constants and regulatory mappings form separate bypasses

`src/cadrumo/domain/invoices/enums.py:33` encodes IVA slots 0, 2, 4, 5, 7.5,
10, and 21 as enum strings and returns the operative percentage at
`src/cadrumo/domain/invoices/enums.py:212`. The dated schedule exists at
`src/cadrumo/_data/registry/aeat/iva/rates.toml:14`. Static regulatory
projections also occur in `src/cadrumo/core/irnr.py:211`,
`src/cadrumo/domain/contribuyente/renta_codes.py:18`,
`src/cadrumo/core/result_disposition.py:113`, and
`src/cadrumo/core/foreign_asset_obligation.py:67`.

### Applicability dates require classification before migration

Candidates include amendment cutoffs at
`src/cadrumo/core/amendment_kind_regime.py:149`, a Madrid 2025 deduction gate at
`src/cadrumo/application/modelo/profile_binding.py:857`, and DANA timing at
`src/cadrumo/application/calculations/m303_regimen_simplificado.py:127`.
Conversely, `src/cadrumo/domain/contribuyente/inventory/valuation.py:121`
appears to state implementation coverage rather than law. Enrollment must
distinguish governed fact, product policy, implementation coverage, protocol
constant, and extraction logic.

### Resolution is fragmented even when the data is sound

Revision parameters use the calculation registry; global legal parameters use
`src/cadrumo/domain/calculations/registry/loader.py:121`; IVA rates use
`src/cadrumo/domain/iva/rates.py:46`; categories use
`src/cadrumo/domain/categories/registry.py:53`; treaties use
`src/cadrumo/domain/calculations/registry/convenio.py:204`; and authorisation
scopes use `src/cadrumo/domain/auth/apoderamientos/catalogue.py:20`.

### This inventory is a baseline, not a completeness proof

The scans covered production ASTs, semantic names, usages, and data
counterparts. Computed expressions, generated artefacts, narrative-only legal
values, and semantically equivalent values with different representations
remain possible false negatives.

### Retirement ledger: delete statutory declarations, not the configuration module

The statutory block in `src/cadrumo/core/external_constants.py:531` through
`src/cadrumo/core/external_constants.py:822` is a symbol-by-symbol deletion
target after migration. The module, `ExternalConstants`, and
`load_external_constants` remain because they also own MIME types, encodings,
output language, endpoints, paths, and other operational configuration.

The governed declarations cover M347 thresholds, low-value goods, Modelo 840
and Modelo 202 thresholds, work-income declaration limits, Art. 7p, Art. 20 and
Art. 52 amounts, modelo classification sets, maritime and maternity values,
descendant ages and windows, shared-custody proration, DT12 rates and windows,
SAL rate and multiplier, and the DEHU notification deadline. Each declaration
is deleted only after every production consumer resolves the corresponding fact
with provenance.

### Retirement ledger: direct consumers must lose static imports

The M347 duplicate paths in
`src/cadrumo/domain/calculations/registry/_m347_threshold.py:23`,
`src/cadrumo/application/aggregation/_counterpart.py:329`,
`src/cadrumo/domain/modelos/row_models.py:1067`, and
`src/cadrumo/application/modelo/calculate_input.py:566` must converge before
the declarations disappear. Other rewiring targets include
`src/cadrumo/domain/calculations/registry/applicability_modelo202.py:118`,
`src/cadrumo/application/modelo/_art20_advisory.py:76`,
`src/cadrumo/application/modelo/_art52_advisory.py:117`,
`src/cadrumo/domain/renta/maritime_exemption.py:242`,
`src/cadrumo/domain/deadlines/models.py:817`, the descendant and family modules
under `src/cadrumo/domain/contribuyente`,
`src/cadrumo/domain/modelos/dt12_reduccion.py:164`,
`src/cadrumo/domain/modelos/sal_reserva_especial.py:53`,
`src/cadrumo/core/notificacion_estado_servicio.py:101`, and
`src/cadrumo/domain/contribuyente/inventory/records.py:769`.

These files generally remain as domain behaviour or facades. Their constant
imports, defaults, fallback schedules, and local value interpretations are the
parts retired.

### Retirement ledger: bespoke IVA readers and caches are conditional deletions

After an authority provider owns typed rows, date and selector resolution,
overlap refusal, evidence closure, fingerprints, and invalidation, delete the
raw parser and cache lane in `src/cadrumo/domain/iva/rates.py:46` through
`src/cadrumo/domain/iva/rates.py:279` and relocate then delete
`src/cadrumo/_data/registry/aeat/iva/rates.toml` from its old authority path.
`IvaRateTableRepository` in
`src/cadrumo/core/resources/_repos/iva_rate_tables.py:17` is deleted if the
authority cache replaces it; otherwise it survives only as a TOML-unaware thin
facade.

Apply the same condition to `load_recargo_rate_table`, its cache, hydration,
reference coercion, and overlap functions in
`src/cadrumo/domain/iva/recargo_equivalencia.py:198`, and to
`src/cadrumo/_data/registry/aeat/iva/recargo-rates.toml`. Preserve the public
record and lookup contracts as provider projections until their callers have
migrated.

Delete `src/cadrumo/domain/iva/_grounding.py:39` only after facts validation
owns the evidence checks for rates, recargo, the IVA catalogue, place of
supply, and verification codes. It is currently an independent catalogue,
fingerprint, and citation-validation path.

### Retirement ledger: numeric IVA enum interpretation is deleted, taxonomy remains

In `src/cadrumo/domain/invoices/enums.py:212`, delete
`_NUMERIC_RATE_PREFIX`, `_slot_declared_percentage`, and the current local
derivation performed by `iva_rate_slot_percentage`, `numeric_iva_rate_slots`,
and `numeric_iva_rate_percentages` after slot-plus-date resolution exists. Keep
`IvaRate`, its persisted tokens, nonnumeric slots, and `IvaRateKind`; persisted
wire taxonomy must not be renumbered as a side effect.

### Retirement ledger: legal-only loaders retire only after their last caller

`load_legal_parameters_only` in
`src/cadrumo/domain/calculations/registry/loader.py:121` is a conditional
retirement API. Its current callers include IVA recargo, transaction retention
rates, activity-selector code sets, and objective-estimation advisory logic.
It can disappear only after the provider represents both scalar rates and
classification sets without duplicating the existing legal TOML authority.

The raw parser/cache portions of `src/cadrumo/domain/categories/registry.py:53`,
`src/cadrumo/domain/iva/catalogue.py:38`, and
`src/cadrumo/domain/iva/place_of_supply.py:187` are conditional targets when
their structured families are enrolled. Their public domain resolution
facades remain. `src/cadrumo/domain/auth/apoderamientos/catalogue.py:76` enters
this campaign only if its externally controlled taxonomy classification is
confirmed.

### Explicit non-removals constrain the campaign

Existing modelo parameter fragments remain where they are. The facts authority
may project them but does not move or duplicate them. Geographic vocabulary,
topic-navigation metadata, MIME types, encodings, output-language settings,
AEAT endpoints, OAuth paths, and other operational configuration are outside
the retirement scope. Mixed geographic/legal helpers must be split and
classified before any deletion.

## Sources

- `src/cadrumo/core/external_constants.py:531`
- `src/cadrumo/core/external_constants.py:822`
- `src/cadrumo/external_constants.toml:1`
- `src/cadrumo/application/aggregation/_counterpart.py:334`
- `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/parameters/0001-threshold.toml:9`
- `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2025-y-siguientes/parameters/0001-threshold.toml:9`
- `src/cadrumo/_data/registry/aeat/categories/trabajador_del_mar.toml:23`
- `src/cadrumo/domain/renta/maritime_exemption.py:279`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0067-renta-2025-maternidad-art-81-1.toml:1`
- `src/cadrumo/application/modelo/profile_binding.py:390`
- `src/cadrumo/domain/invoices/enums.py:33`
- `src/cadrumo/domain/invoices/enums.py:212`
- `src/cadrumo/_data/registry/aeat/iva/rates.toml:14`
- `src/cadrumo/core/irnr.py:211`
- `src/cadrumo/domain/contribuyente/renta_codes.py:18`
- `src/cadrumo/core/result_disposition.py:113`
- `src/cadrumo/core/foreign_asset_obligation.py:67`
- `src/cadrumo/core/amendment_kind_regime.py:149`
- `src/cadrumo/application/modelo/profile_binding.py:857`
- `src/cadrumo/application/calculations/m303_regimen_simplificado.py:127`
- `src/cadrumo/domain/contribuyente/inventory/valuation.py:121`
- `src/cadrumo/domain/calculations/registry/loader.py:121`
- `src/cadrumo/domain/iva/rates.py:46`
- `src/cadrumo/domain/categories/registry.py:53`
- `src/cadrumo/domain/calculations/registry/convenio.py:204`
- `src/cadrumo/domain/auth/apoderamientos/catalogue.py:20`
