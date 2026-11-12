---
tags:
  - '#adr'
  - '#renta-rental-income-source'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:5821045668a71a7a5e0cc795daf2446e1d8a796486827de6732d4c1b8eb7c30f'
related:
  - "[[2026-09-03-unreachable-capability-fincas-titularidad-adr]]"
  - "[[2026-09-02-unreachable-capability-fincas-unblock-research]]"
  - "[[2026-10-30-assets-core-disposal-adr]]"
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-operator-layer-adr]]"
---
# `renta-rental-income-source` adr: `rental income source for Modelo 100 inmueble rows` | (**status:** `accepted`)

Accepted 2026-11-11 by CADRUMO-PRIME under the operator's delegation of ADR acceptance (confirmed 2026-11-11), together with its two amendments: the fincas titularidad record and one more absence-attestation family in the prior-carry attestation record.

## Problem Statement

Modelo 100 has no source for rendimientos del capital inmobiliario. Every casilla of the `Inmuebles/Inmueble` group (0063 to 0154, with the anexo detail rows 1210 to 1224 and 1392 to 1440) is a manual casilla with no binding in every supported edition, measured as described under Considerations. Nothing under `src/cadrumo/application` aggregates rental income into those rows. The profile has no property or lease record. The only rental path is the year-keyed leaf `renta_rental.reduccion_art_23_2_tier_2024` (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1476-1488`), consumed by one 2024 binding (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0001-declarations.toml:1-6`) and removed again in 2025 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/revision.toml:8747-8749`). The return of a landlord therefore omits its main income, or carries it only as hand-typed scalar casillas.

The rental engine named by `2026-09-03-unreachable-capability-fincas-titularidad-adr` (`Finca`, the `rental_fincas` tables) no longer exists. It was removed as unreachable code on 2026-09-08 (`src/cadrumo/domain/fincas/` and `src/cadrumo/adapters/persistence/profile/fincas.py`, commit `11b7e28445`). Its titularidad ruling stands; its storage does not.

## Considerations

- Measurement of unsourced casillas. For each year of the envelope (2022 to 2026; 2026 projects from the 2025 edition) the hydrated snapshot was passed through the canonical data-inventory bucketing, `collect_inventory_buckets` (`src/cadrumo/application/modelo/data_inventory.py:323-357`). A casilla counts as unsourced when its `input_kind` is manual and no binding targets it. Row-field templates (`src/cadrumo/domain/calculations/registry/casilla_membership.py:93-111`) number zero for Modelo 100 in every year, because its layout is an XML dictionary whose repetition comes from row bindings. The inmueble casillas are therefore scalar manual. `modelo edit` refuses only row-field templates (`src/cadrumo/application/modelo/edit_admission.py:166-175`), and a scalar value lands in at most one `Inmueble` occurrence (`src/cadrumo/application/filing/export_xml_dictionary.py:157-172`). That is a one-property, hand-typed path, not a source.
- Repeated rows already have a mechanism. The `activity_asset_disposal` family emits row-grain values with `fact = "row_field"` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:888`), and the XML export places row values into the repeating elements the XSD declares (`src/cadrumo/application/filing/export_xml_dictionary.py:762-800`). `Inmueble` admits 180 occurrences (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:4664`).
- The official design is stable across editions. Each dictionary for 2022 to 2025 declares 164 rows under `/Inmuebles/Inmueble/` with the same contract date (0093), reduction flag (0100) and reduction amount (0150): 2025 `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:161-262`; the 2024 dictionary (file prefix `08-100`) lines 205-256; 2023 (`07-100`) lines 192-243; 2022 (`06-100`) lines 188-239. The registry manual counts in the group differ (148, 148, 147, 127 for 2022 to 2025). That is a registry inventory difference to reconcile, not a design difference.
- One occurrence per property, contracts nested. The 2025 XSD repeats `Inmueble` 0 to 180 times (`03-100-esquema-xsd-ejercicio-2025-actualizado-24-06-2026-793-kb-ejecutable.xsd:4664`) and nests `Arrendamiento` 0 to 3 times inside it (line 4818); casillas 0102 to 0154 occur once per `Inmueble`. The Renta 2025 manual apportions the expenses of the year by contract duration (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:12723-12746`).
- Amortisation rule. 3 per cent of the greater of the acquisition cost attributable to the construction and the cadastral value excluding land (LIRPF art. 23.1.b, RIRPF art. 14; 2025 manual lines 11815-11830 and 12032-12034; 2024 line 11771; 2023 line 11346; 2022 line 9387). Without a known land value the cost is split by the IBI cadastral ratio (2025 lines 11836-11838). Cumulative amortisation is capped at the acquisition value excluding land (lines 11839-11866, TEAC 00/00653/2025). The worked example at lines 11885-11907 is an oracle. The rate exists as `renta-rental-amortizacion-rate` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/parameters/0001-declarations.toml:1112`).
- Reduction rule. Before 2024 a qualifying dwelling lease reduces positive net income by 60 per cent (2023 manual line 11373; 2022 line 9413). From 1 January 2024, contracts concluded from 26 May 2023 take 50, 60, 70 or 90 per cent by facts fixed when the contract is signed. Earlier contracts keep 60 per cent under DT 38.a LIRPF (2024 manual lines 11831-11836 and 12490; 2025 lines 12090-12139 and 12752-12762). Tier rates, rehabilitation look-back, the 18 to 35 age band and the 5 per cent rent cut are registry parameters (the 2020 parameters file above, lines 898-1020). The regime change is held only as the year-valued `renta-rental-ejercicio-amendment-year = 2024` (line 883); the 26 May 2023 cut-off is absent.
- Titularidad. Attribution by a required regime plus casillas 0063 and 0064 is decided in `2026-09-03-unreachable-capability-fincas-titularidad-adr`, grounded in `2026-09-02-unreachable-capability-fincas-unblock-research`.
- The ledger cannot carry the link today. `Transaction` has `irpf_category` (vocabulary value `capital_inmobiliario`, `src/cadrumo/_data/registry/aeat/facts/0128-irpf-income-category-vocabulary.toml:64-67`) but no property or lease reference and no capital-inmobiliario expense concept (`src/cadrumo/domain/transactions/models.py:557-609`). The spending categories are activity categories (`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:1175`). The Modelo 210 `asset_or_right_id` is free text (`src/cadrumo/domain/transactions/m210_income_classification.py:236`).
- Retired keys. A previous profile `properties` section was retired; a stored fact at a removed path is refused as unknown (`src/cadrumo/application/user_profile/tests/test_retired_profile_field_paths.py:21-33`).
- Other Modelo 100 groups with neither a source nor a multi-row entry path, measured as above for 2025 (manual, no binding; where a group repeats, only one scalar occurrence can be typed). This decision does not solve them:
  - capital mobiliario: 0027 to 0039 (ahorro), 0043 to 0044 (DT 4.a), 0046 to 0055 (general);
  - imputacion de rentas inmobiliarias: 0083 to 0089, inside the inmueble group;
  - ganancias patrimoniales: funds 0311 to 0322 and 2225 to 2234, shares 0327 to 0338, rights 0342 to 0353, other elements 0357 to 1652, other inmuebles 0413 to 2243 (bound only where an activity asset is disposed of), crypto 1801 to 1879, prizes 0266 to 0362, earlier-ejercicio gains 0389 to 0395, reinvestment 0399, exit-tax rows 0401 to 0410;
  - anexo A: housing and energy-improvement deductions 0683 to 0710 and 1655 to 1779, rental deduction 0715 to 0720, donations 0722 to 0725, business investment 0706 to 2061, Canarias and Baleares reserves 0733 to 0802 and 1681 to 1943, electric vehicles 1916 to 1935;
  - anexo B: regional deductions for every community, with their information blocks 0638 to 2184;
  - anexo C: carries and excesses 1231 to 2048, including negative bases 1379 to 1389;
  - special regimes 0161 to 1622 and 0257 to 0278; base reductions 0382 to 0499; objective estimation 0238 to 1481 and the agrarian group from 0157.

## Considered options

- Hand entry on the form: keep scalar `modelo edit` entry. Rejected: one property at most, no amortisation or reduction derivation, figures typed onto the return.
- Annual totals on the property record. Rejected by the coordinator ruling: amounts come from the ledger, and a typed annual total cannot be reconciled with its rows.
- A dedicated rental register outside the profile, as `rental_fincas` was. Rejected: it duplicates custody, revision, history and door machinery the profile already has, and the removed tables show that a register without a door goes unused.
- Reuse `category_id` with new spending categories. Rejected: activity categories carry proportionality and IVA treatments that do not apply to capital inmobiliario, and a mixed vocabulary invites misrouting.
- Chosen: profile-held property and lease records, two typed optional ledger fields, one row-grain source family, and the reduction tier derived from lease facts and dated registry data.

## Constraints

- No year appears in a profile key, binding id, fact key or parameter id. The reduction regime is selected by dated registry data on the devengo axis and by the contract date.
- Years come only from `src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`. Bindings are authored at the earliest edition and amended only where the dictionary of an edition differs. A projected year reaches calculation grade at most.
- No missing fact becomes zero. A missing required fact refuses the affected occurrence with a typed reason and a door. A disposition the law requires but this decision does not compute is a blocking finding, never an omitted row.
- Amounts come only from ledger rows. The property and lease records hold identification, structural and contract facts, never an annual total.
- Private facts (cadastral reference, address, tenant NIF, contract terms) persist only in exact-profile encrypted custody.
- The titularidad ruling of `2026-09-03-unreachable-capability-fincas-titularidad-adr` binds unchanged; only its storage moves.

## Implementation

We will source the Modelo 100 `Inmueble` rows from profile property and lease records and from ledger rows linked to them, through one row-grain source family used by pull, preview, calculation and export for every supported year.

Property record. A repeatable, effective-dated profile section `renta_inmueble` with a stable row key, declared in `schema.toml` and entered through its own door, following the `renta_family.descendiente` precedent. A new key is required because `properties` was retired with another meaning. Fields:

- identification: referencia catastral (0066), situacion clave (0065), urbana or rustica (0067, 0068), address (0069);
- titularidad: the regime, titular role and the two percentages of the 09-03 ruling (0063, 0064);
- acquisition: onerosa or lucrativa (0118, 0119), acquisition date (0120), transmission date when applicable (0121), acquisition amount (0126; the ISD value for a lucrative acquisition), acquisition expenses and taxes (0127), the land value when the deed states one, and improvements made before the ledger covers the property, each dated;
- cadastral values, effective-dated by IBI year: total (0123) and construction (0124);
- uses other than letting, as dated intervals: habitual dwelling, at the disposal of the owner, afecto to an activity;
- an accessory property is its own property row naming its principal; its amortisation is a blocking finding until computed;
- an attested cumulative amortisation to the start of the first ejercicio the app computes, required only where the cumulative cap can bind.

Lease record. A repeatable section `renta_arrendamiento` that references one property row key. Fields: contract date (0093); start and end dates; dwelling use, the art. 23.2 precondition; tenant NIFs with the foreign-NIF flag (0091 to 0098 and the unnumbered tenant 4 to 9 rows); and the facts fixed at signing that decide the reduction. Those facts are: tensioned residential-market zone, first letting of the dwelling, the age band of each natural-person tenant, a public-administration or qualifying-entity tenant with its purpose, the completion date of a rehabilitation, the initial rent and the last updated rent of the previous contract, and whether the tenant is a relative within the art. 24 degree.

Ledger link, the smallest change. `Transaction` gains two optional typed fields. `arrendamiento_ref` links an income row to one lease, and through it to the property. `inmueble_ref` plus a registry-declared `gasto_capital_inmobiliario` concept link an expense row to a property. The concept vocabulary is a new dated registry fact mapping each token to its casilla: financing interest 0105, repair and conservation 0106, community 0109, contract formalisation 0110, legal defence 0111, third-party services 0112, supplies 0113, insurance 0114, taxes 0115, doubtful debts 0116, other 0148, and improvement, which is capitalised into 0129 and never expensed. A row carries at most one of the two links, and the link is what makes it a capital-inmobiliario row. A linked row whose classification bears business figures must also carry `irpf_category = capital_inmobiliario`, a token added to the ledger taxonomy; a linked personal row carries none. Withholding feeds 0153 from the suffered-withholding record whose payer is a tenant of the property's lease. The profile refuses removal of a property or lease that a ledger row references.

Aggregation. One `BindingSourceKind` for the rental rows, enrolled in the shared source dispatch beside the `activity_asset_disposal` family, with no modelo-name branch. Row grain is one `Inmueble` occurrence per property held in the ejercicio. Each lease active in the ejercicio is a per-contract part of its property, computed separately and summed into the property's casillas. For each occurrence:

- 0102 is the sum of linked income rows, imputed by exigibilidad;
- expenses linked to the property are apportioned to its leases by days let under each lease;
- 0101 and 0122 come from lease dates;
- 0103 and 0104 come from the occurrence with the same property row identity in the earlier Modelo 100 the application holds; where it holds none, from the operator's attestation of absence or of the amounts by origin year;
- 0105 to 0108 and the anexo rows 1210 to 1224 apply the art. 23.1.a cap;
- the amortisation chain 0124 to 0131 follows the rule in Considerations, prorated by days let;
- the 0063 or 0064 share applies after the whole-property figures, as the 09-03 ruling requires.

The cumulative cap is proven not to bind only when the base is the acquisition side and the calendar years from acquisition through the ejercicio times the rate do not exceed one. Otherwise the attested cumulative figure is required.

Reduction. 0100 and the 0150 rate are derived, never entered. No reduction applies to a lease that is not for a dwelling or that breaches art. 17.6 LAU. The registry replaces `renta-rental-ejercicio-amendment-year` with dated data: a regime fact valid from 2024-01-01 on the devengo axis, carrying the contract cut-off date 2023-05-26 (DT 38.a LIRPF; Ley 12/2023, DF 9.a). A legacy 60 per cent rate parameter cites DT 38.a and the pre-2024 text. The derivation is:

- devengo before the regime, or contract before the cut-off: legacy 60 per cent;
- otherwise 90 per cent for a tensioned-zone lease whose rent was cut by more than the threshold against the previous contract;
- otherwise 70 per cent where, in a tensioned zone, the dwelling is let for the first time to tenants aged 18 to 35, or is let to a qualifying public administration or non-profit entity; in the law's words, where only some tenants meet the age condition the 70 per cent applies to the part of the net income that proportionally corresponds to them (LIRPF art. 23.2). The application does not compute that proportional case: a lease where only some tenants qualify is a blocking finding;
- otherwise 60 per cent for a rehabilitation completed within the look-back before the contract;
- otherwise 50 per cent.

The 2024 formula over the profile binding (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0001-declarations.toml:1-24`) is replaced by this derived rate at row grain.

Refusals and doors. A missing required fact refuses its occurrence with a registered, localised reason naming the property or lease and the door that fixes it. Examples: titularidad not declared; cadastral values for the year absent; contract date absent; a reduction fact absent for a contract after the cut-off; an income row without a lease link while the profile declares rental. Every frontend renders the served reason and authors none. Doors:

- `aeat config profile inmueble add|edit|list|remove`;
- `aeat config profile arrendamiento add|edit|list|end|remove`;
- `aeat app ledger classify TX --arrendamiento REF` for income rows;
- `aeat app ledger classify TX --inmueble REF --gasto-inmobiliario CONCEPT` for expense rows.

Blocking findings, not computed by this decision. Each keeps the affected value unresolved:

- imputacion de rentas inmobiliarias (0083 to 0089) for non-let days;
- the art. 24 minimum (0152) for a lease to a relative;
- the usufructo amortisation already refused by the 09-03 ruling;
- concurrent leases of parts of one property, whose expense apportionment basis is not grounded.

Not computed and not offered, shown as a non-blocking limitation: furniture amortisation (0117) and the art. 23.3 irregular reduction (0151). The limitation is served on every rental occurrence at verification and in the export result; it names the boxes and says the return may overstate the tax. The principle, which binds every lane: an item the application does not compute is a blocking finding when leaving it out could lower the tax or misstate an identifying fact, and may be a non-blocking limitation only when leaving it out can only raise the tax and no stored fact shows it applies.

Migration. Remove `reduccion_art_23_2_tier_2024`, the `renta_rental` section, the `binding.profile_key` entry of the tier catalogue (`src/cadrumo/_data/registry/aeat/facts/0121-renta-rental-reduccion-art-23-2-tier-catalogue.toml:42`), the 2024 profile binding, and the schema comment at `schema.toml:19`. A stored profile holding the removed key is migrated once, through the profile write boundary, with a history event. The migration clears the value and raises a finding that asks the operator to record the lease facts; a tier cannot be converted into those facts. After migration the removed path is refused as unknown, like the other retired paths.

Verification and export. Verification reports each refused occurrence and each blocking finding. A projected year reports `registry_filing_year_projected` and stops at calculation grade. The calculation revision records a digest of each property row, lease row and withholding record it consumed, the ledger fingerprint covers the link fields, and the drift gate compares both at verification. Export emits one `Inmueble` element per occurrence through the existing repeated-row path, refuses more occurrences than the XSD admits, and never emits an occurrence that carries a refusal. Bound casillas leave scalar manual entry.

Hypotheses that may change within these constraints: field names, the source-kind name, and whether the expense concept has its own fact or a new family in an existing vocabulary fact.

Reconciliation of existing records. Proposed edits, applied only on approval:

- `2026-09-03-unreachable-capability-fincas-titularidad-adr`: add an amendment section stating that the titularidad value object and attribution rule attach to the `renta_inmuebles.inmueble` record. Its `Finca` record, `rental_fincas` mapper row and schema-version paragraph describe code removed on 2026-09-08. Its unencrypted titular column no longer applies, because every field is held in encrypted profile custody. The rule, the refusals and the oracles stand.
- `2026-11-08-prior-carry-attestation-adr`: add an amendment admitting one more absence-attestation family, `renta_capital_inmobiliario_gastos_pendientes`, at row grain keyed by the property row identity (amended 2026-11-12 to match the accepted 23:25 ruling: situaciones 4 and 5 hold no referencia catastral and it is an editable fact, so the property row identity is the key). Without it, a first year in the app cannot state an absent 0103.
- `2026-09-30-modelo-editor-workbench-operator-layer-adr` and `2026-09-21-assets-core-lifecycle-contract-adr`: no edit. Bound row columns become non-writable under the existing source-kind rule, and the asset lifecycle already excludes rental income.

## Rationale

The profile already gives exact-profile encrypted custody, effective dating, stable row keys, revision guards and the `aeat config profile` door family, so the property and lease records gain them without a second store. Two typed ledger fields are the least change that keeps amounts on the rows that prove them; no existing field can express a property or a lease. A row-grain source family reuses the mechanism that already carries asset disposals into repeating XML elements. A dated cut-off removes the year-keyed tier and the year-valued amendment parameter together, and makes 2022 to 2025 one derivation.

## Consequences

- Rental income, expenses, amortisation and reduction reach the return from records, for any number of properties and contracts up to the XSD bound.
- Profiles holding the retired tier key need the one-time migration, and the operator re-enters the lease facts.
- Several rental dispositions remain blocking findings until decided, so some landlords see an unresolved return instead of a wrong one.
- Reconsider if a later dictionary changes the `Inmueble` group, if an official source settles the 1 to 3 per cent amortisation reading the 2025 manual draws from STS 1502/2025 (lines 11867-11880), or if a basis for apportioning expenses among concurrent leases is grounded.

## Amendment 2026-11-11: decisions ruling

Accepted 2026-11-11 23:25 by CADRUMO-PRIME on the ruling of the operator's one-time decisions agent for rental income (seven changes, two with conditions), and written into the body above: one occurrence per property with leases as per-contract parts; the link marks a rental row and only a business-bearing linked row carries `capital_inmobiliario`; the pending-expense carry is matched by property row identity, else attested; the revision records per-record consumption digests that the drift gate compares; 0117 and 0151 move to a served non-blocking limitation under the stated principle; an accessory property is its own row; the 70 per cent tenant branch keeps the law's proportional rule and a partly qualifying lease is a blocking finding, and no reduction applies on an art. 17.6 LAU breach. The record names are the sections `renta_inmueble` and `renta_arrendamiento`, which also corrects the dotted names in the 09-03 amendment. Points the ruling could not settle remain blocking findings or the stated judgements (days rather than twelfths; the 3 per cent ceiling); none is an operator choice.
