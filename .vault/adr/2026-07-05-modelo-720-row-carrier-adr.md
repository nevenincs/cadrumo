---
tags:
  - '#adr'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-10-03'
body_hash: 'sha256:9d87c2a2a6e5fd206de560beea0773185ad618630bbce53ac0a5c0b6200cf8c2'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-adr]]"
  - "[[2026-06-02-modelo-720-prior-year-baseline-research]]"
  - '[[2026-09-11-binding-schema-adr]]'
  - '[[2026-08-22-source-casilla-integration-adr]]'
  - '[[2026-07-21-ledger-fx-conversion-adr]]'
  - '[[2026-10-02-binding-consumer-closure-modelo-720-fx-research]]'
---

# `modelo-720-prior-year-baseline` adr: `M720 row-carrier source mesh` | (**status:** `accepted`)

## Problem Statement

Modelo 720 now has a correct row taxonomy and a resolver that can validate
declarable foreign-asset rows against the live registry. The remaining blocker
is the carrier: `resolve_foreign_asset_binding_row_values` returns values keyed
as `(binding_id, row_index)`, but `CalculationSourceResolution.binding_values`
is a scalar binding channel keyed only by `binding_id`. The M720 resolver
therefore validates the row projection and discards it, preserving only
provenance and source transaction ids. That is honest but insufficient for live
mesh enrollment, draft replay, or export parity.

This ADR decides how row-indexed Modelo 720 binding values move through the
source mesh and calculation/draft surfaces without flattening repeat rows into
fake scalar binding ids and without repurposing unrelated detail-row DTOs.

## Considerations

- The registry row-binding resolver already has the correct M720 value shape:
  a real `BindingId`, a 1-based row index, and a scalar field value. That is the
  same identity that the filing draft surface already models through
  `ModeloBindingValue.row_index`.
- `CalculationSourceResolution` currently has scalar binding channels
  (`binding_values`, `enum_binding_values`, `date_binding_values`) and a
  `detail_rows` channel. The scalar channels cannot represent repeat rows
  without corrupting the binding-id namespace.
- `detail_rows` is not a binding-value channel. It carries typed domain row DTOs
  such as M184/M232/M347/M349 rows, is content-addressed on the calculation
  revision, and is rendered/exported as row objects. Modelo 720's registry
  output is already expressed as binding ids plus row indexes, not as a
  committed M720 domain row DTO.
- The source-connectivity ADR names `CalculationSourceResolution` as the single
  resolved-source carrier and already anticipated detail-row data. The missing
  piece is the row-indexed binding-value channel that bridges registry row
  bindings to draft/replay/export.
- The D9 resolver-contract audit explicitly blocked M720 promotion because the
  foreign-assets resolver had no row-indexed envelope channel. This decision is
  the named follow-up for that blocker.

## Considered options

- Flatten repeat rows into synthetic scalar binding ids such as
  `binding_id:row-1`. Rejected because it invents registry identifiers the
  registry does not declare, bypasses binding-id validation, and makes row order
  part of a string convention instead of typed state.
- Reuse `detail_rows` and add a Modelo 720 row DTO. Rejected for this campaign
  because it duplicates the registry row-binding resolver output and loses the
  direct `BindingId` -> row field relationship the draft/export layer needs.
- Add a first-class row-indexed binding-value map to
  `CalculationSourceResolution`. Chosen because it preserves real registry
  binding ids, carries the 1-based row index as typed data, composes with the
  existing merge envelope, and projects directly to `ModeloBindingValue` records
  with `row_index`.

## Constraints

- No new binding source kind, resolver convention, validator convention, or
  registry grouping is introduced. `foreign_asset` remains the source kind and
  `per_foreign_asset` remains the row grouping.
- The carrier must preserve the exact registry `BindingId`; the row index is a
  separate typed coordinate and must be 1-based.
- The scalar calculation engine remains scalar. Row-indexed binding values are
  for draft/replay/export and live-mesh parity, not formula-runtime inputs.
- Merge semantics must stay exclusive by `(binding_id, row_index)`. Two
  resolvers may not claim the same row-binding coordinate in the same mesh tier.
- The parent features are stable enough to build on: the source mesh is the
  canonical resolver envelope, the filing draft already supports
  `ModeloBindingValue.row_index`, and the foreign-asset registry row resolver is
  real-behavior tested against live M720 bindings.

## Implementation

Add a row-indexed binding-value channel to the source mesh envelope. The channel
is a typed map whose key is `(BindingId, row_index)` and whose value is the
registry row field scalar (`Decimal` or `str` for the current M720 resolver).
The field should be named for binding values, not detail rows, so consumers do
not confuse it with `detail_rows`.

`merge_source_resolutions` and the precedence merge carry this map just like
the scalar binding channels, but collision detection is keyed by the full
`(binding_id, row_index)` coordinate. The foreign-assets resolver returns the
validated output from `resolve_foreign_asset_binding_row_values` through this
channel.

The calculation/draft assembly layer carries the row-indexed values into
`ModeloBindingValue` with the same `binding_id`, the scalar value, the binding's
legal/source refs, `source = foreign_asset`, and the row index. Replay/export
must preserve the row coordinate as a structured field; it must not join the row
number into the binding id string.

## Rationale

The chosen carrier is the smallest shape that preserves the registry contract
end to end. The domain resolver already returns `(BindingId, row_index)` because
that is the actual identity of a field in a repeating record. Carrying that
shape through the mesh prevents two silent failures: scalar collapse, where
only one row survives per binding id, and synthetic-id drift, where downstream
code treats fabricated keys as registry facts.

Reusing `detail_rows` is attractive because it already travels through the mesh,
but it is the wrong abstraction for M720 binding parity. `detail_rows` carries
domain row DTOs whose fields are exported as row objects. The M720 blocker is
not missing a row DTO; it is missing the ability to move registry-declared
row-binding values from a resolver into draft/replay/export with their binding
grounding intact.

## Consequences

- The M720 resolver can stop discarding validated registry row values and can
  prove live mesh parity against the per-modelo aggregation output.
- Draft and replay surfaces can carry row-indexed binding values using the
  existing `ModeloBindingValue.row_index` concept.
- The calculation engine remains scalar; formulas do not consume row-indexed
  M720 detail fields unless a separate ADR later decides a formula-facing row
  fold.
- Merge and serialization code must gain tests for collision handling,
  deterministic ordering, and JSON-safe replay of tuple-keyed row coordinates.
- This ADR unlocks W03 implementation and later `FOREIGN_ASSET` enrollment, but
  it does not itself remove `FOREIGN_ASSET` from the deferred source set.

## Amendment 2026-10-02: type 2 record composition from asset identity, class-routed slots, source-owned precedence and euro conversion

Authorization basis: Confirmed by the user on 2026-10-02 after review of the concrete rulings.

This amendment refines the accepted ruling above. The accepted body stays as it is. The row-indexed `(BindingId, row_index)` carrier is still the transport. This section decides how a Modelo 720 type 2 record is assembled before rows are indexed: which identity joins a ledger-sourced asset to the operator-declared fields of the same record, which wire slot each row field fills for each asset class, who owns a slot when both sides supply it, and how a foreign-currency value becomes the euro amount the record design requires.

### Problem Statement

The six `foreign_asset` row bindings declare `record = "bien"`, and no export record claims that name. The type 2 record (`binding_record = "type_2"`) is claimed only by `manual_input` record-field bindings. The row bindings are therefore unconsumed (`UNCONSUMED_FILING_GRADE_BINDING`), and there are three reasons they cannot simply be renamed onto `type_2`.

- **No join identity.** Source rows are numbered by position after a sort on `(country, class, identifier, acquisition date)` (`src/cadrumo/domain/calculations/registry/detail_record_bindings.py:217-234`), and the observation's `source_id` is dropped from the row. Operator row values are also numbered by position (`src/cadrumo/application/filing/draft_construction.py:738-761`). The two meet only at the row index. Adding an asset that sorts earlier shifts every later index, which attaches one asset's operator data to another. A `type_2` scalar `manual_input` value (row index `None`) never reaches an emitted row at all. The accepted `2026-08-22-source-casilla-integration-adr` already holds the M720 composite at `grounding_blocked` "until a typed persisted asset identity is established or a separately approved, uniqueness-enforced composite key is grounded".
- **Class-conditional placement.** One source fact maps to different official slots depending on position 102: an account identifier goes to 144 and 156-189, a securities identifier to 131 and 132-143, and S and B carry no identifier slot (Orden HAP/72/2013 Anexo, type 2 pos. 131-189). The existing `row_field_casilla_ids` map is one row field to one casilla (`src/cadrumo/domain/calculations/registry/export.py:483-498`).
- **Currency has no slot.** Every amount must be "en euros o su contravalor" (type 2 pos. 432-446 and 447-461). The source observation either arrives pre-converted with no rate provenance (`valuation_eur`, `src/cadrumo/application/aggregation/foreign_assets.py:130`) or carries a currency label that nothing converts (`src/cadrumo/application/calculations/row_set_assembly.py:772`).

### Considerations

- The official record grain is one type 2 record per asset, per declarant condition (pos. 76) and per incorporation date (pos. 415-422): "puede existir más de un registro para cada bien o derecho en función de la distinta condición … y las distintas fechas de adquisición" (Orden HAP/72/2013 Anexo, descripción de los registros). The valuation is not prorated across co-holders (pos. 432-446: "el importe NO se prorrateará").
- Official identifiers do not identify every asset uniquely. B has no identifier field, only an address (pos. 251-414). S has only the insurer's name and NIF (pos. 190-250). A security without an ISIN is coded `ZXX`, where XX is the issuer country (pos. 132-143). Only C (IBAN or another account code) and V/I with an ISIN are unique by their official field.
- The class-code taxonomy is settled (`2026-07-05-modelo-720-prior-year-baseline-adr`, class-code record), and this amendment consumes it unchanged.
- `binding-schema` requires one registration authority per provider kind and refuses unreferenced filing-grade bindings without a disposition (`2026-09-11-binding-schema-adr`). The compiler admits one claimant per export slot.
- Euro conversion already has one canonical port: the `ExchangeRateProvider` protocol, composed by the host and backed by the ECB adapter. Missing rates and transport failures refuse there; they never produce zero (`2026-07-21-ledger-fx-conversion-adr`; Ley 46/1998 art. 36 per `2026-06-02-ledger-fx-conversion-research`).
- The exchange rate is the ECB euro reference rate: Ley 46/1998 art. 36 defines the cambio oficial as the rate the ECB publishes for the euro, which the Banco de España republishes unchanged in the BOE. No Modelo 720 provision fixes a rate or a rate date; DGT consultas vinculantes fix the date per class and situation, and the AEAT valuation FAQ is supporting guidance only. Evidence: `2026-10-02-binding-consumer-closure-modelo-720-fx-research`.
- The renderer turns two overlapping active binding fields on one row into two separate records (`src/cadrumo/application/filing/record_renderer.py:263-280, 387-398`). Two claimants on one 720 slot would therefore duplicate a record instead of refusing it.

### Considered options

- **Join on row index (status quo).** Rejected. The index is a sort artifact, so the attachment error described above is built into it.
- **Join on a composite key derived from the official identifier per class.** Rejected. The key is not unique for B, S and V/I without an ISIN. The accepted source-integration ruling forbids fabricating a transient key, and accepting this option would require a separate key-grounding decision that the official design cannot support.
- **Join on an explicit typed asset identity persisted once and carried by both sides.** Chosen. It is unique by construction, survives across ejercicios (which origin `M` and the 20.000 EUR re-declaration test need), and lets the official identifier serve as a cross-check rather than as the key.
- **Route class-specific slots in Python.** Rejected. This would be a modelo-specific branch.
- **Split identifier bindings per class with a row filter on the provider.** Rejected. Per-binding row filters give each binding its own row numbering. The existing `asset_classes` cohort filter already picks an arbitrary cohort when bindings differ (`detail_record_bindings.py:210-212`).
- **A typed, total, class-conditional row-field route on the export record.** Chosen. Placement is declared as record-design data, one binding per source fact.
- **Keep the operator's type 2 fields as scalar `manual_input` bindings beside the row source.** Rejected. Scalars cannot address rows, and two families would claim one record.
- **Assemble every per-record field in the `foreign_asset` row source after the identity join.** Chosen. There is one row family, one index space, and the join happens before any row is numbered.

### Constraints

- The accepted body's constraints stand except where this amendment widens them. `foreign_asset` remains the only source kind and `per_foreign_asset` the only grouping. No new provider kind is introduced.
- Widened: `ForeignAssetProvider` gains the row fields listed below and loses `asset_classes`. Its registration admits the terminal origins `detail_record` (ledger or worksheet observation) and `operator_input` (operator declaration entry). The export-record schema gains one generic typed declaration, the class-conditional row-field route. Both changes happen inside the `binding-schema` registration authority and need no amendment to that record.
- No positional, sorted or fabricated key may join source data and operator data. Row indexes are assigned only after the join, deterministically from the record key.
- One claimant per slot. A slot is owned either by the source row family or by a declaration-level field, never by both.
- An unconvertible amount, an unmatched record side or an unrouted class is a refusal or a missing-input diagnostic. It is never zero, blank or a default.

### Implementation

We will assemble each Modelo 720 type 2 record from one joined row family keyed by a typed persisted asset identity. Placement comes from a total, class-routed declaration in the registry, source-owned fields are locked against operator override, and every amount is converted to euros through one ECB-rate path dated by the record design.

**1. Join identity.**

- A foreign asset is identified by `M720AssetRef`, an opaque identifier minted once by an encrypted foreign-asset register in the declarant's profile store and never reused.
- Each register entry holds the asset's class (position 102 code), country (129-130), subclave (103) and official identifier, with a typed identifier scheme: IBAN, other account code, ISIN, or no ISIN with issuer country. The register refuses a second entry with the same class and the same official identifier when that identifier is unique by scheme (IBAN, account code, ISIN).
- Every source observation, whether a ledger or a worksheet row, carries `asset_ref`. The ledger keeps `source_object_id` only as provenance.
- Operator declaration entries are addressed by `(asset_ref, clave de condición)`.
- The type 2 record key is `(asset_ref, clave de condición, fecha de incorporación)`. The resolver joins on `asset_ref`, fans out one record per declared condition for each source lot (incorporation date), and assigns row indexes in the order of the record key. The full valuation is repeated on each condition's record and is never prorated.
- When a source observation's official identifier differs from its register entry, the resolver refuses and names the `asset_ref`.

**Unmatched sides.**

- If a source asset has no operator declaration entry, the record lacks condición (76) and porcentaje (476-480). Filing-grade export refuses with a structured missing-input diagnostic (modelo 720, revision, `asset_ref`, field ids, source family `foreign_asset`). The resolver never defaults the condición to `1` or the porcentaje to `100`.
- If an operator declaration entry has no source observation for the ejercicio, the source-owned slots have no value. Export refuses with a diagnostic naming the `asset_ref`. The operator supplies the observation through the ledger or the worksheet, or records the extinction (origin `C`, which still needs its valuation and date).
- A declaration entry naming an `asset_ref` that the register does not hold is refused at write.
- A declaration entry for an asset in a non-declarable obligation block is not exported and is reported as an advisory.
- A ledger observation and a worksheet row for the same `asset_ref` in one ejercicio are a collision and are refused. Today the worksheet silently replaces every ledger observation when both are present (`foreign_assets.py:358-359`).

**2. Slot ownership and per-class routing (registry data).**

- Source-owned row fields: 102 class, 129-130 country, the identifier and its key (131 and 132-143, or 144 and 156-189), 415-422 incorporation date, and 432-446 valuation 1.
- Operator-owned row fields, entered on the declaration entry or the register: 76, 77-101, 103, 104-128, 145-155, 190-230, 231-250, 251-414, 423, 424-431, 447-461, 462, 463-474, 475 and 476-480.
- Declaration-level record-constant fields: 5-8 and 9-17 are copied from type 1, and 18-26 and 36-75 hold the declarant (pos. 5-75 descriptions). These render as the existing `draft` and `header` field kinds on every record and stop being per-row inputs. Field 27-35 (representante legal) is a declaration-level operator fact rendered identically on every record and blank when there is no representative.
- The `type_2` export record declares a route for each class-conditional row field: the row field, the discriminating row field (`asset_class_code`), and for each M720 class code either a target slot or `design_blank` with its record-design citation.
  - Account and securities identifiers route as listed above.
  - 131 and 144 are emitted from the identifier scheme.
  - 103 is zero for `I`.
  - 104-128 is used only for `B` subclave 5.
  - 190-250 is blank for `B`.
  - 462-474 is used only for `V` and `I`.
  - 475 is used only for `B`.
  - 447-461 is used only for `C` with origin `A` or `M`, or for `B` with origin `C`.
- The compiler refuses a route table that is not total over the five codes, a target outside the record, or two routes reaching one slot. The renderer fills a `design_blank` slot with the design's empty fill: zeros for numeric fields, spaces for alphanumeric ones.
- Valuation 1 carries a typed valuation basis per class and subclave, declared in the registry, with an edition for the ejercicio 2023+ insurance text (Orden HFP/1180/2023). The bases are:
  - C: balance at 31 December, or at cessation.
  - V: balance or value at 31 December, or at extinction.
  - I: valor liquidativo.
  - S1: rescate, or provisión matemática from 2023.
  - S2: capitalización, or rescate when the rent comes from a life policy.
  - B1: acquisition value including taxes.
  - B2-4: value at 31 December under Ley 19/1991.
  An observation whose basis differs from the declared one is refused.

**3. Precedence.**

- `FOREIGN_ASSET` joins the `deterministic_lock` tier of the caller-override ladder (`src/cadrumo/application/aggregation/source_mesh.py:447`).
- An operator value for a source-owned field of an asset that has a source observation is rejected at the write boundary (calculate and the edit contract), and the refusal names the asset, field and source. The source value is never silently dropped and never silently replaced.
- A stored revision that already holds such a disagreement is refused for amend, verify and export, with an instruction to recalculate (the precedent is `src/cadrumo/application/modelo/stored_row_field_input_gate.py:19-52`).
- The re-declaration evidence keeps reading source rows independently of the operator's declaration (`src/cadrumo/application/calculations/foreign_asset_redeclaration.py:323-410`). Its comparison is unchanged.

**4. Currency.**

- No new conversion mechanism. Modelo 720 converts through the existing canonical port and nothing else:
  - The `ExchangeRateProvider` protocol, defined at `src/cadrumo/domain/currency/service.py:29-49`.
  - The provider is resolved from the host-composed seam `exchange_rate_provider()` (`src/cadrumo/application/exchange_rate_provider.py:39-45`), which installed hosts bind to the ECB adapter (`src/cadrumo/entrypoints/exchange_rate_composition.py:18-32`; `src/cadrumo/adapters/outbound/fx/ecb_provider.py:67-131, 236-243`).
  - The arithmetic is `CurrencyNormalizationService.normalize(amount, rate_date)` (`src/cadrumo/domain/currency/service.py:52-103`): native-EUR passthrough, CCY to EUR multiplication, cent rounding, and a rate-source stamp.
  - The foreign-asset resolver calls that service with the rate date below. It does not reimplement lookup, inversion, look-back or rounding, and it never constructs a transport.
  - Tests compose the recorded rate tables (`recorded_fx_*`), where an unrecorded pair is refused. Only `aeat_live` tests reach the ECB.
- Each monetary input carries its native amount, its ISO 4217 currency and its valuation event (31 December, or cessation or extinction with its date). The ingest model's `valuation_eur` is replaced by these fields, and EUR inputs carry `EUR`.
- **Valuation date versus rate date.** The record design fixes the valuation date for each class, meaning the date at which the amount is measured (Orden HAP/72/2013 Anexo, type 2 pos. 432-446; consolidated text in the corpus, `orden-hap-72-2013.html.extracted.md:380-390`):
  - C: balance at 31 December, or at cessation.
  - V: balance at 31 December, or at extinction.
  - I: valor liquidativo at 31 December, or at extinction.
  - S: rescate or capitalización value at 31 December.
  - B subclave 1: acquisition value.
  - B subclaves 2-4: value at 31 December.
  - Valuation 2 (pos. 447-461) is the account's last-quarter average, or the real-estate transmission value for origin `C`.

  The Orden fixes no exchange-rate date ("en euros o su contravalor en los casos de operaciones de divisas"). The rate is the ECB reference rate (Ley 46/1998 art. 36) and its date follows DGT doctrine (`2026-10-02-binding-consumer-closure-modelo-720-fx-research`). The 720 resolver supplies this legal rate date to the port; it never uses the operation date:
  - Accounts (C): the 31 December balance and the last-quarter average are both converted at the 31 December rate (V0691-13). The average is computed in the original currency first and then converted, and a multi-currency account is one record (V1133-22).
  - Every other valuation at 31 December (V, I, S, B subclaves 2-4): the 31 December rate of the declared year (V0555-18, V1096-18, V3973-15, V0751-25, V1051-26).
  - Real-estate acquisition value (B subclave 1): the 31 December rate of the declared year, not the acquisition-date rate (V2669-17). That euro value is then frozen for the 20.000 EUR re-declaration test.
  - Extinction or transfer during the year: the rate at the extinction date. Filing grade for accounts (cessation) and for transferred real estate (V1051-26, V2045-23).
  - A 31 December that falls on a non-publication day uses the last ECB publication before it, within the port's bounded look-back.
- **Threshold tests.** The 50.000 EUR block threshold and the 20.000 EUR re-declaration increase run on the converted euro values. Exchange-rate movements count for every block except real estate, whose acquisition value stays frozen in euros (V2669-17). The comparison base is the last declaration filed for the block ("la última declaración", RD 1065/2007 arts. 42 bis.5, 42 ter.5, 54 bis.7), not the previous year; accounts are tested on both the 31 December balance and the last-quarter average.
- **Missing rate.** The port's own refusal semantics apply. `normalize` reports a missing rate as `CurrencyNormalizationStatus.MISSING_RATE`, and the provider maps an unknown currency to `ExchangeRateProviderError` (`ecb_provider.py:143-149`). Both carry a placeholder `eur_amount` of `0.0` (`service.py:75-88`). The 720 resolver accepts only `NATIVE_EUR` or `NORMALIZED` and never reads `eur_amount` from any other status. `MISSING_RATE` or `UNSUPPORTED_CURRENCY` becomes a structured missing-input refusal naming the `asset_ref`, currency and rate date. A transport failure (`ExchangeRateProviderError`) propagates as a refusal. No path yields zero.
- The `NormalizedAmount` rate, rate date and `rate_source` are fingerprinted on the row's source identity and provenance. The same normalized euro values feed the 50.000 EUR block threshold, the type 2 rows and the type 1 totals.
- The `modelo-720-asset-row-currency` binding is retired, because currency is a conversion input carried in provenance and the design has no slot for it.

**5. Type 1 totals.**

- 136-144 is the number of emitted type 2 records.
- 146-162 and 164-180 are the signed sums of type 2 433-446 and 448-461 (sign at 145/163, from type 2 432/447). Both derive from the emitted type 2 rows through the canonical aggregation, as the design defines them.
- The three `manual_input` total bindings are retired.

**6. Migration.**

- Registry, on the authored `2013-y-siguientes` edition:
  - Retarget the five remaining `foreign_asset` bindings to `record = "type_2"` with a row-field export projection.
  - Add the operator-owned row-field bindings (same `foreign_asset` kind, `operator_input` origin).
  - Retire the type 2 `manual_input` bindings whose slots become row-owned or declaration-level, and the type 1 total bindings.
  - Declare the routes.
  - Normalise with the edition delta migration and regenerate the form layout.
- Code: the worksheet assembler's silent defaults (class `C`, currency EUR, valuation 0, acquisition date 31 December; `row_set_assembly.py:745-776`) become missing-input refusals.
- Stored data: no positional row can be re-keyed to an `asset_ref` deterministically, so no automatic migration is attempted. A stored Modelo 720 revision whose rows carry no `asset_ref`, or whose `binding_overrides` name a retired binding, stays readable as history and is refused for amend, verify and re-export with a recalculate instruction. No compatibility reader or fallback is kept. No released compatibility floor exists.

**7. Required proof.**

All tests run through the real registry, resolver and renderer.

- **Positive:** an IBAN account in USD, a two-lot ISIN security and a real-estate asset produce byte-exact type 2 and type 1 records against an independently authored expected fichero built from the record design.
- **Fan-out:** one account with conditions 1 and 3 produces two records with the full valuation on each.
- **Detector teeth:** adding an asset that sorts first leaves every operator field on its own asset.
- **Exclusion:** a non-declarable block is excluded and its declaration entry produces an advisory. A virtual-currency observation is refused.
- **Missing:** a source asset without a declaration, a declaration without a source, a missing rate or currency, and each worksheet field that previously had a default.
- **Mismatch:** an operator override of a source-owned field, a register/observation identifier conflict, and a ledger plus worksheet collision for one asset.
- **Currency:** a 31 December rate on a weekend falls back to the prior publication, and an account closed mid-year uses the cessation-date rate. Both use recorded ECB fixtures.
- **Routes:** isolated temporary registries prove that a non-total route table and two routes to one slot are refused.
- **Gate:** the 720 contribution to `check-bindings` is zero.
- **Round trip:** the export parser reads the fichero back to the same typed records.

### Rationale

Only an explicit persisted identity satisfies all three constraints together: the record design's per-asset, per-condition, per-date grain, the non-uniqueness of official identifiers for B, S and securities without an ISIN, and the accepted refusal to fabricate a foreign-asset key. Joining before indexing removes the positional hazard at its cause instead of guarding it afterward. Declaring routes on the export record keeps placement as record-design data under one mechanism, consistent with the aggregation and binding rules, and makes an unhandled class a compile-time refusal. Locking source-owned fields reuses the existing caller-override ladder rather than inventing a second precedence rule. The rate date follows AEAT's published practice, and the rate source follows the accepted fx decision, and conversion reuses the existing port, so there is no second FX path and no modelo-local rate table.

### Consequences

- The six `foreign_asset` findings close: five bindings are consumed through `EXPORT_BINDING_RECORD` and the currency binding is retired. The Modelo 720 composite meets the source-integration reopening condition for a typed persisted asset identity.
- Operators register each foreign asset once, and they declare their condition and the descriptive fields per asset rather than per row position.
- The amendment adds an encrypted register, a schema route declaration, a renderer fill for `design_blank`, and a refusal for stored pre-identity revisions. This is materially larger than the S06 text in `2026-10-02-binding-consumer-closure-plan` and needs the plan's S06 scope widened through the plan verbs.
- The rate rule is grounded in Ley 46/1998 art. 36 and the DGT consultas recorded in `2026-10-02-binding-consumer-closure-modelo-720-fx-research`; the AEAT valuation FAQ is supporting guidance and its capture into the corpus is a follow-up, not a filing-grade precondition.
- Reconsider this amendment if AEAT publishes a type 2 asset identifier, if a later edition changes the record grain, or if a published rule settles the open rate-date cases below differently.
- Open points the official sources leave unsettled stay advisory. Filing-grade export refuses for them until they are grounded:
  1. Weekend or holiday fallback for an extinction-date rate.
  2. Currencies the ECB does not publish (for example ARS, CUP, VES, CLP, COP, RUB since 2022): the DGT says "ECB at 31 December", which cannot be applied literally.
  3. The rate for listed shares valued at a last-quarter average price (V1059-13 left it unanswered).
  4. The acquisition-value rate in a real-estate extinction record.
  5. Securities, IIC and insurance extinguished during the year (extinction-date rate by analogy only).
  6. A real-estate asset first declared in a later year.
  - **B subclave 5.** The design gives no valuation basis for "otros derechos reales" (it names subclave 1 and subclaves 2-4 only).
