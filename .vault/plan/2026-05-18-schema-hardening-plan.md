---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-18'
modified: '2026-05-18'
tier: L2
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-18-schema-hardening-research]]'
---


# `schema-hardening` Plan A: `data_type` Literal extension plan

### Phase `P01` - introduce `nif` data_type and retrofit casilla-bearing modelos

This Phase delivers the `nif` semantic type with Spanish NIF / NIE /
CIF check-digit validation, retrofits the four casilla-bearing modelos
identified by the identity-atom inventory, and discovers remaining
header-only NIF surfaces.

- [x] `P01.S01` - extend `data_type` Literal with `"nif"` variant; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S02` - add `NifString` `Annotated` alias with `BeforeValidator` enforcing NIF / NIE / CIF format and check digit; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S03` - add strict roundtrip test covering valid Spanish NIF, NIE, and CIF inputs plus failure cases; `src/aeat/domain/calculations/registry/test_nif_data_type.py`.
- [x] `P01.S04` - retrofit modelo 180 perceptor-NIF and retenedor-NIF casillas to `data_type = "nif"`; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `P01.S05` - retrofit modelo 184 perceptor-NIF casillas to `data_type = "nif"`; `src/aeat/_data/registry/aeat/modelos/184.toml`.
- [x] `P01.S06` - audit modelo 349 NIF surfaces; `declarante NIF is header-level (defer to S09 expansion) and op.nif-comunitario is NIF-IVA (defer to long-tail P06.S76 nif_iva phase); `.vault/audit/2026-05-18-schema-hardening-nif-coverage.md`.
- [x] `P01.S07` - retrofit modelo 100 declarante NIF, spouse NIF, descendant NIF, and ascendant NIF casillas across all revisions to `data_type = "nif"`; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `P01.S08` - sweep remaining modelos for header-only or binding-selector NIF surfaces and emit a discovery note enumerating the retrofit list; `.vault/audit/2026-05-18-schema-hardening-nif-coverage.md`.
- [x] `P01.S09` - header-only NIF retrofits across modelos other than M100/180/184/349; `deferred pending Plan C semantic_role rollout which subsumes header-vs-casilla normalisation; `.vault/audit/2026-05-18-schema-hardening-nif-coverage-m100.md`.
- [x] `P01.S10` - type-based label-pattern validator rejecting text NIF declarations; `superseded by Plan C W01.P01.S04 semantic_role consistency validator which enforces the same property through role binding; deferred without implementation; `.vault/plan/2026-05-20-schema-hardening-plan.md`.

### Phase `P02` - introduce `year` data_type and retrofit ejercicio casillas

This Phase delivers the `year` semantic type with a bounded-integer
validator matching `RegistrySnapshotRef.filing_year`, and retrofits
the `decl.ejercicio` casilla on every modelo per the fiscal-period
inventory.

- [x] `P02.S11` - extend `data_type` Literal with `"year"` variant; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P02.S12` - add `FilingYear` `Annotated` alias with bound `ge=2000, le=2099`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P02.S13` - add strict roundtrip test covering valid and out-of-range year inputs; `src/aeat/domain/calculations/registry/test_year_data_type.py`.
- [x] `P02.S14` - modelo 036 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/036.toml`.
- [x] `P02.S15` - modelo 100 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/100.toml`.
- [x] `P02.S16` - modelo 111 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/111.toml`.
- [x] `P02.S17` - modelo 115 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/115.toml`.
- [x] `P02.S18` - modelo 123 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/123.toml`.
- [x] `P02.S19` - modelo 130 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `P02.S20` - modelo 131 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/131.toml`.
- [x] `P02.S21` - retrofit modelo 180 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `P02.S22` - retrofit modelo 184 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/184.toml`.
- [x] `P02.S23` - modelo 190 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/190.toml`.
- [x] `P02.S24` - modelo 193 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/193.toml`.
- [x] `P02.S25` - modelo 200 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/200.toml`.
- [x] `P02.S26` - modelo 202 has no casilla-level decl.ejercicio; `ejercicio is exposed via export header_key only and falls under a future ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/202.toml`.
- [x] `P02.S27` - retrofit modelo 232 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/232.toml`.
- [x] `P02.S28` - retrofit modelo 303 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/303.toml`.
- [x] `P02.S29` - retrofit modelo 308 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/308.toml`.
- [x] `P02.S30` - retrofit modelo 309 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/309.toml`.
- [x] `P02.S31` - retrofit modelo 322 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/322.toml`.
- [x] `P02.S32` - retrofit modelo 347 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/347.toml`.
- [x] `P02.S33` - retrofit modelo 349 `decl.ejercicio` and `rect.ejercicio-rectificado` casillas to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/349.toml`.
- [x] `P02.S34` - retrofit modelo 353 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/353.toml`.
- [x] `P02.S35` - retrofit modelo 360 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/360.toml`.
- [x] `P02.S36` - retrofit modelo 369 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/369.toml`.
- [x] `P02.S37` - retrofit modelo 390 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/390.toml`.
- [x] `P02.S38` - retrofit modelo 720 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `P02.S39` - retrofit modelo 840 `decl.ejercicio` casilla to `data_type = "year"`; `src/aeat/_data/registry/aeat/modelos/840.toml`.
- [x] `P02.S40` - type-based decl.ejercicio integer-rejection validator; `superseded by Plan C semantic_role consistency validator which enforces filing_year role uniformity across all year-bearing casillas; deferred; `.vault/plan/2026-05-20-schema-hardening-plan.md`.

### Phase `P03` - introduce `period_code` data_type and retrofit periodo casillas

This Phase delivers the `period_code` semantic type with a Literal
union covering quarterly, monthly, annual, IS-instalment, and OSS
period codes, and retrofits every `decl.periodo` casilla per the
fiscal-period inventory.

- [x] `P03.S41` - extend `data_type` Literal with `"period_code"` variant; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P03.S42` - add `PeriodCode` `Annotated` alias with Literal covering `1T..4T`, `1P..4P`, `0A`, `01..12`, and `EXT-1T..EXT-4T`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P03.S43` - add strict roundtrip test covering each period family plus failure cases for unknown codes; `src/aeat/domain/calculations/registry/test_period_code_data_type.py`.
- [x] `P03.S44` - sweep all 26 modelos and emit a discovery note enumerating every casilla, header_key, or binding selector carrying a period value, with the period family declared per modelo; `.vault/audit/2026-05-18-schema-hardening-period-coverage.md`.
- [x] `P03.S45` - expansion placeholder closed; `the period-coverage audit shows only 7 casilla instances across 5 modelos already retrofitted in-line during P03, no further expansion needed; `.vault/audit/2026-05-18-schema-hardening-period-coverage.md`.
- [x] `P03.S46` - type-based decl.periodo text-rejection validator; `superseded by Plan C semantic_role consistency validator binding the filing_period role; deferred; `.vault/plan/2026-05-20-schema-hardening-plan.md`.

### Phase `P04` - introduce `country_code` data_type and retrofit country fields

This Phase delivers the `country_code` semantic type with an ISO 3166-1
alpha-2 enumeration plus AEAT-supported extensions, and retrofits the
five modelos identified by the address-atom inventory.

- [x] `P04.S47` - extend `data_type` Literal with `"country_code"` variant; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P04.S48` - add `CountryCode` `Annotated` alias with enumeration enforcement and AEAT-supported extension list; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P04.S49` - add strict roundtrip test covering ISO codes, AEAT extensions, and rejection of unknown codes; `src/aeat/domain/calculations/registry/test_country_code_data_type.py`.
- [x] `P04.S50` - retrofit modelo 100 country-code casillas (1799, ZRUE2) across all revisions to `data_type = "country_code"`; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `P04.S51` - M232 clave-pais is binding-selector-level (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/232.toml`.
- [x] `P04.S52` - retrofit modelo 349 `op.codigo-pais` casilla to `data_type = "country_code"`; `src/aeat/_data/registry/aeat/modelos/349.toml`.
- [x] `P04.S53` - M720 codigo-de-pais is binding-selector-level (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `P04.S54` - country-coverage sweep complete: 6 casilla-level retrofits in M100/M349; `M232 and M720 country fields are binding-selector-level deferred to future ExportField extension; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P04.S55` - country-code text-rejection validator superseded by Plan C semantic_role consistency validator binding the country roles; `deferred; `.vault/plan/2026-05-20-schema-hardening-plan.md`.

### Phase `P05` - introduce `iban` data_type and retrofit IBAN fields

This Phase delivers the `iban` semantic type with IBAN mod-97 check-digit
validation, and retrofits the seven modelos identified by the
banking-atom inventory.

- [x] `P05.S56` - extend `data_type` Literal with `"iban"` variant; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P05.S57` - add `IbanString` `Annotated` alias with IBAN mod-97 validator and BBAN length checks; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P05.S58` - add strict roundtrip test covering valid Spanish and foreign IBANs plus failure cases for malformed values; `src/aeat/domain/calculations/registry/test_iban_data_type.py`.
- [x] `P05.S59` - retrofit modelo 100 IBAN casillas across all retained revisions to `data_type = "iban"`; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `P05.S60` - M111 IBAN is export header_key (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/111.toml`.
- [x] `P05.S61` - M115 IBAN is export header_key (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/115.toml`.
- [x] `P05.S62` - M123 IBAN is export header_key (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/123.toml`.
- [x] `P05.S63` - M130 IBAN is export header_key (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/130.toml`.
- [x] `P05.S64` - M131 IBAN is export header_key (not CasillaDefinition); `retrofit deferred to future ExportField data_type Literal extension; `src/aeat/_data/registry/aeat/modelos/131.toml`.
- [x] `P05.S65` - M720 has no casilla-level IBAN; `the banking inventory cited a foreign-refund BIC at the binding/header level not at CasillaDefinition; defer to future ExportField extension; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `P05.S66` - emit a follow-up audit note documenting the modelo 100 IBAN rectificación drop (casillas 0687, 0688, 1780, 1782, 1783) as an open cross-revision deprecation issue; `.vault/audit/2026-05-18-schema-hardening-iban-deprecation.md`.
- [x] `P05.S67` - iban text-rejection validator superseded by Plan C semantic_role consistency validator binding the iban role; `deferred; `.vault/plan/2026-05-20-schema-hardening-plan.md`.

### Phase `P06` - introduce long-tail semantic data_types and retrofit affected fields

This Phase delivers the long-tail semantic types deferred from earlier
Phases: `name`, `nif_iva`, `ccaa_code`, `province_code`,
`postal_code`, `municipality_code`, `bic`, `date`. Each type follows
the same shape: Literal extension, `Annotated` alias, roundtrip test,
modelo retrofits, validator flip.

- [x] `P06.S68` - extend `data_type` Literal with `"name"` variant and add `PersonOrEntityName` `Annotated` alias with length and non-empty constraints; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S69` - add strict roundtrip test for the `name` alias; `src/aeat/domain/calculations/registry/test_name_data_type.py`.
- [x] `P06.S70` - retrofit modelo 180 naming casillas to `data_type = "name"`; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `P06.S71` - M349 has no perc.nombre casilla; `counterparty names live in op.nombre-comunitario; retrofit deferred until label-pattern sweep confirms scope; `src/aeat/_data/registry/aeat/modelos/349.toml`.
- [x] `P06.S72` - M100 naming surface spans 10 distinct semantic roles (taxpayer, spouse, ascendant, descendant, family-member, entity-legal, related-party) across 6 revisions; `deferred to Plan C taxpayer_name role rollout where role-binding makes the polymorphic split explicit; `.vault/plan/2026-05-20-schema-hardening-plan.md`.
- [x] `P06.S73` - M232 naming surface is binding-selector-level (not CasillaDefinition); `retrofit deferred to future BindingSelector data_type extension; `src/aeat/_data/registry/aeat/modelos/232.toml`.
- [x] `P06.S74` - M720 naming surface is binding-selector-level (not CasillaDefinition); `retrofit deferred to future BindingSelector data_type extension; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `P06.S75` - extend `data_type` Literal with `"nif_iva"` variant and add `NifIvaString` `Annotated` alias; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S76` - add strict roundtrip test for the `nif_iva` alias; `src/aeat/domain/calculations/registry/test_nif_iva_data_type.py`.
- [x] `P06.S77` - retrofit modelo 349 intracomunitario NIF-IVA casillas to `data_type = "nif_iva"`; `src/aeat/_data/registry/aeat/modelos/349.toml`.
- [x] `P06.S78` - extend `data_type` Literal with `"ccaa_code"` variant and add `CCAACode` `Annotated` alias with closed enumeration; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S79` - add strict roundtrip test for the `ccaa_code` alias; `src/aeat/domain/calculations/registry/test_ccaa_code_data_type.py`.
- [x] `P06.S80` - M100 ccaa casillas live in deduction-result subsections with non-uniform ids; `deferred to Plan C semantic_role rollout where role-binding decouples retrofit from id-pattern matching; `.vault/plan/2026-05-20-schema-hardening-plan.md`.
- [x] `P06.S81` - extend `data_type` Literal with `"province_code"` variant and add `ProvinceCode` `Annotated` alias; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S82` - add strict roundtrip test for the `province_code` alias; `src/aeat/domain/calculations/registry/test_province_code_data_type.py`.
- [x] `P06.S83` - retrofit modelo 180 province casilla to `data_type = "province_code"`; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `P06.S84` - M100 province casillas live in deduction-result subsections with non-uniform ids; `deferred to Plan C semantic_role rollout where role-binding decouples retrofit from id-pattern matching; `.vault/plan/2026-05-20-schema-hardening-plan.md`.
- [x] `P06.S85` - extend `data_type` Literal with `"postal_code"` variant and add `PostalCode` `Annotated` alias; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S86` - add strict roundtrip test for the `postal_code` alias; `src/aeat/domain/calculations/registry/test_postal_code_data_type.py`.
- [x] `P06.S87` - retrofit modelo 180 postal-code casilla to `data_type = "postal_code"`; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `P06.S88` - extend `data_type` Literal with `"municipality_code"` variant and add `MunicipalityCode` `Annotated` alias; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S89` - add strict roundtrip test for the `municipality_code` alias; `src/aeat/domain/calculations/registry/test_municipality_code_data_type.py`.
- [x] `P06.S90` - retrofit modelo 180 municipality casilla to `data_type = "municipality_code"`; `src/aeat/_data/registry/aeat/modelos/180.toml`.
- [x] `P06.S91` - M100 municipality casillas live in deduction-result subsections with non-uniform ids; `deferred to Plan C semantic_role rollout where role-binding decouples retrofit from id-pattern matching; `.vault/plan/2026-05-20-schema-hardening-plan.md`.
- [x] `P06.S92` - 131-municipality-fichero-BOE-binding: not at CasillaDefinition layer; `retrofit deferred to future BindingSelector or ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P06.S93` - extend `data_type` Literal with `"bic"` variant and add `BicString` `Annotated` alias; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S94` - add strict roundtrip test for the `bic` alias; `src/aeat/domain/calculations/registry/test_bic_data_type.py`.
- [x] `P06.S95` - 100-BIC-not-found-as-casilla: not at CasillaDefinition layer; `retrofit deferred to future BindingSelector or ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P06.S96` - 720-BIC-binding-level: not at CasillaDefinition layer; `retrofit deferred to future BindingSelector or ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P06.S97` - extend `data_type` Literal with `"date"` variant and add `CalendarDate` `Annotated` alias with declared format contract; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P06.S98` - add strict roundtrip test for the `date` alias; `src/aeat/domain/calculations/registry/test_date_data_type.py`.
- [x] `P06.S99` - 232-date-export-header_key: not at CasillaDefinition layer; `retrofit deferred to future BindingSelector or ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P06.S100` - 202-date-export-header_key: not at CasillaDefinition layer; `retrofit deferred to future BindingSelector or ExportField data_type extension; `src/aeat/_data/registry/aeat/modelos/`.
- [x] `P06.S101` - long-tail validator hard-flip superseded by Plan C semantic_role consistency validator covering all long-tail roles; `deferred; `.vault/plan/2026-05-20-schema-hardening-plan.md`.
