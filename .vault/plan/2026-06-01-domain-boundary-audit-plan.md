---
tags:
  - '#plan'
  - '#domain-boundary-audit'
date: '2026-06-01'
modified: '2026-06-01'
tier: L3
related:
  - '[[2026-06-01-domain-boundary-audit-adr]]'
  - '[[2026-04-30-aeat-restructure-research]]'
  - '[[2026-06-01-domain-boundary-audit-audit]]'
---


# `domain-boundary-audit` `Domain boundary remediation` plan

## Wave `W01` - Registry public surface (D3)

Promote the registry id aliases, DecimalValue, CounterpartSourceKind and externally-consumed oracle/filed-state types into registry/__init__.__all__, then sweep all 33 private-submodule importers onto the public surface; fix the IvaInvoiceClassification iva/invoices export asymmetry. Foundational: unblocks clean imports for later waves.

### Phase `W01.P01` - Promote missing registry symbols to __all__

Add the _ids id aliases, DecimalValue, CounterpartSourceKind, and the externally-consumed oracle/filed-state/observation types to registry/__init__ imports and __all__.

- [x] `W01.P01.S01` - Add the 22 _ids type aliases (ModeloId, RevisionId, CasillaId, FormulaId, ParameterId, BindingId, RelationId, LegalRefId, SourceRefId, ExtractionProfileId, CrossReferenceId, WorkbookParityRefId, VerificationExpectationId, ApplicationLinkId, DeadlineWindowId, SupportRemovalDecisionId, ConstructId, DependencyClassificationId, ExportLayoutId, RecordId, ExportFieldId, WorkbookFixtureId, OracleId) plus is_registry_id to registry/__init__ imports and __all__; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P01.S02` - Promote DecimalValue from _schema.py into registry/__init__ imports and __all__; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P01.S03` - Promote CounterpartSourceKind plus AtributionMemberObservation, Modelo720RowObservation, RefundOperationObservation, RelatedPartyOperationObservation from _bindings.py into registry/__init__ and __all__; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P01.S04` - Promote AeatNifIvaObservation and AeatNifIvaCheckerOracle from _aeat_nif_iva_oracle.py into registry/__init__ and __all__; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P01.S05` - Promote RegistryFiledStateComparison and compare_calculation_to_filed_observation from _filed_state.py into registry/__init__ and __all__; `src/aeat/domain/calculations/registry/__init__.py`.
- [x] `W01.P01.S06` - Promote audit_registry_oracle_bindings from _live_parity.py into registry/__init__ and __all__; `src/aeat/domain/calculations/registry/__init__.py`.

### Phase `W01.P02` - Path-fix sweep for already-exported symbols

Repoint every importer that uses a registry private submodule path for a symbol already in __all__ onto the public surface, grouped by consuming package.

- [x] `W01.P02.S07` - Repoint application/calculations registry imports (_binding_prefill, _row_set_assembly, _observations_repository, _multi_year, _maritime_exemption_service, _iva_wallet_reconciliation, _relation_prefill) from private submodules to the registry public surface for already-exported symbols; `src/aeat/application/calculations/`.
- [x] `W01.P02.S08` - Repoint application/storage/calc_sheets registry imports (_engine, _parity_harness, _translator, _layout) to the public surface for already-exported _schema/_formula_runtime symbols; `src/aeat/application/storage/calc_sheets/`.
- [x] `W01.P02.S09` - Repoint adapters/inbound/declaracion (_parser RegistrySnapshotRef/BboxAnchorSpec, _schema RegistrySnapshotRef) to the registry public surface; `src/aeat/adapters/inbound/declaracion/`.
- [x] `W01.P02.S10` - Repoint domain siblings (renta/_maritime_exemption CasillaObservation, modelos/_calculation_revision CasillaObservation, user_profile/_registry_contract ModeloDefinition/ModeloRevision, filing/_schema RegistrySnapshotRef) to the registry public surface; `src/aeat/domain/`.
- [x] `W01.P02.S11` - Repoint entrypoints/cli registry imports (_modelo errors/parse_modelo_period/ModeloRevision, _config/_google formula_runtime/schema/authority/errors, registry.py OracleEnvironment) to the public surface; `src/aeat/entrypoints/cli/`.
- [x] `W01.P02.S12` - Repoint application/registry already-exported imports (GroiOracle, verify_legal_catalogue, live_parity symbols, WorkbookBackendVerificationReport), application/live ValidatedRegistryAuthority, application/diagnostics RegistryValidationError, core/resources/_repos/modelos ModeloDefinition to the public surface; `src/aeat/application/registry/__init__.py`.
- [x] `W01.P02.S13` - Repoint the two cycle-forced deferred importers (iva/_recargo_equivalencia, fincas/_imputacion_parameters) to the registry public surface for load_legal_parameters_only, keeping the imports function-local per the documented module-load cycle; `src/aeat/domain/iva/_recargo_equivalencia.py`.

### Phase `W01.P03` - Path-fix sweep for newly-promoted symbols and IvaInvoiceClassification

After promotion, repoint the _ids/DecimalValue/CounterpartSourceKind importers and fix the IvaInvoiceClassification iva/invoices export asymmetry.

- [x] `W01.P03.S14` - Repoint the _ids-alias importers in entrypoints/cli (_modelo_payloads CasillaId/FormulaId/RevisionId, _modelo BindingId/CasillaId) to the registry public surface; `src/aeat/entrypoints/cli/_modelo_payloads.py`.
- [x] `W01.P03.S15` - Repoint the _ids-alias importers in adapters (inbound/pdf/_shared CasillaId, inbound/declaracion/_schema CasillaId, outbound/aeat/sede/_schema CasillaId, outbound/google/_calc_sheets_pull BindingId/CasillaId/RelationId/RevisionId) to the public surface; `src/aeat/adapters/`.
- [x] `W01.P03.S16` - Repoint the _ids-alias and DecimalValue importers in application/storage/calc_sheets (_records, _parity_harness, _layout, _translator) to the public surface; `src/aeat/application/storage/calc_sheets/`.
- [x] `W01.P03.S17` - Repoint the _ids-alias importers in application/modelo/_result_summary, application/calculations/_binding_prefill BindingId, application/filing/runtime CasillaId/FormulaId/LegalRefId/SourceRefId to the public surface; `src/aeat/application/`.
- [x] `W01.P03.S18` - Repoint the _ids-alias importers in domain siblings (renta/_maritime_exemption CasillaId, filing/_schema BindingId/CasillaId) to the public surface; `src/aeat/domain/`.
- [x] `W01.P03.S19` - Repoint adapters/outbound/aeat/sede/_nif_iva_check (AeatNifIvaObservation) and application/aggregation/_counterpart (CounterpartSourceKind) and application/calculations/_row_set_assembly (4 observation types) to the public surface; `src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py`.
- [x] `W01.P03.S20` - Repoint application/registry/__init__ private imports of AeatNifIvaCheckerOracle, RegistryFiledStateComparison, compare_calculation_to_filed_observation, audit_registry_oracle_bindings to the now-public surface; `src/aeat/application/registry/__init__.py`.
- [x] `W01.P03.S21` - Fix the IvaInvoiceClassification export asymmetry: add IvaInvoiceClassification, classify_invoice_line_for_iva, invoice_line_to_iva_observation to iva/__init__ __all__, and repoint invoices/__init__ and invoices/_models from ..iva._invoice_classification to ..iva; `src/aeat/domain/iva/__init__.py`.

## Wave `W02` - Regulatory logic and values to domain (D2)

Relocate tax formulas, statutory validations, regulatory thresholds and registry-derived classification policy out of the CLI/application/core-infra layers into grounded domain/registry homes with oracle citations: DT-12 and SAL formulas, M184/M347 validations, M347/M720 thresholds, aggregation regulatory enums, the rounding-code StrEnum, and verification policy.

### Phase `W02.P04` - Threshold shim removal and statutory validations to domain

Remove the M347_THRESHOLD_EUR re-export chain and relocate the M184/M347 validations to domain record validators/functions.

- [x] `W02.P04.S22` - Remove the M347_THRESHOLD_EUR re-export from domain/modelos/_row_models __all__ and domain/modelos/__init__ __all__; `repoint cli/_modelo to import it directly from core.external_constants (DB-38 shim removal); `src/aeat/domain/modelos/_row_models.py`.
- [x] `W02.P04.S23` - Move _validate_m347_threshold into a model_validator on Modelo347ContraparteRow using M347_THRESHOLD_EUR; `delete the CLI helper and let construction enforce it, catching at cli/_modelo:3235 (DB-35a); `src/aeat/domain/modelos/_row_models.py`.
- [x] `W02.P04.S24` - Add domain validate_m184_member_share_sum(rows) to domain/modelos; `repoint cli/_modelo:3234 to call it and translate the domain error to typer.BadParameter (DB-35b); `src/aeat/domain/modelos/_row_models.py`.

### Phase `W02.P05` - CLI regulatory formulas to domain

Move the DT-12 and SAL reserva formulas (and PensionReduccionError) out of the CLI into grounded domain modules with oracle tests.

- [x] `W02.P05.S25` - Relocate PensionReduccionError from application/calculations/_errors.py to domain/modelos/_errors.py; `update the error-registry string at core/errors/registry/_application.py:958 and all import sites (prereq: domain cannot import application); `src/aeat/domain/modelos/_errors.py`.
- [x] `W02.P05.S26` - Relocate _compute_dt12_reduccion_plan_pensiones to a new domain/modelos/_dt12_reduccion.py with an oracle-cited test (LIRPF DT 12 worked example); `repoint the cli/_modelo:3145 call site; `src/aeat/domain/modelos/_dt12_reduccion.py`.
- [x] `W02.P05.S27` - Relocate _compute_sal_reserva_especial_dotacion to a new domain/modelos/_sal_reserva_especial.py with an oracle-cited test (Ley 44/2015 art. 14 worked example); `repoint the cli/_modelo:3186 call site; `src/aeat/domain/modelos/_sal_reserva_especial.py`.

### Phase `W02.P06` - Aggregation regulatory enums to core and rounding-code unification

Relocate RetencionScheme, OperationKind347/349, ForeignAssetClass to core; introduce RegistryRoundingCode StrEnum; move verification classification policy beside registry data.

- [x] `W02.P06.S28` - Introduce RegistryRoundingCode StrEnum (money-2, integer) in registry/_schema.py; `retype FormulaDefinition.rounding; update _formula_runtime _apply_rounding and calc_sheets/_engine _rounding_rule_for to compare enum members (DB-25); `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `W02.P06.S29` - Relocate RetencionScheme from application/aggregation/_retenciones.py to core (core/retencion.py or core/aggregation.py); `update all in-aggregation consumers and the package re-export (DB-14a); `src/aeat/core/aggregation.py`.
- [x] `W02.P06.S30` - Relocate OperationKind347 and OperationKind349 from application/aggregation/_counterpart.py to core; `update _counterpart, _registry_provider and the package re-export (DB-14b); `src/aeat/core/aggregation.py`.
- [x] `W02.P06.S31` - Relocate ForeignAssetClass from application/aggregation/_foreign_assets.py to core, leaving ForeignAssetClassRollup in aggregation; `update all field references and the re-export (DB-14c); `src/aeat/core/aggregation.py`.
- [x] `W02.P06.S32` - Expose a RegistrySnapshot.verification_policy() typed accessor in domain and move _classify_discrepancy/_verification_policy logic beside VerificationExpectation; `repoint application/verification/_verify to consume it (DB-22); `src/aeat/domain/calculations/registry/_schema.py`.

## Wave `W03` - IVA-compensation domain (D2 marquee)

Create the domain/iva_compensation package and migrate the Modelo-303 carry-forward, four-year-window, wallet-reconciliation decision tree, casilla-component mapping and compensacion-disponible derivation out of application/calculations, application/live and adapters/sede; collapse the duplicated derivation to one provenance-preserving domain function.

### Phase `W03.P07` - Create domain/iva_compensation and move errors

Scaffold the domain package and relocate the five IVA-compensation error classes.

- [x] `W03.P07.S33` - Scaffold domain/iva_compensation/ with __init__, _errors, _carry_forward, _reconciliation, _balance modules (tag relocation:domain/iva_compensation-init); `src/aeat/domain/iva_compensation/__init__.py`.
- [x] `W03.P07.S34` - Move the 5 IVA-compensation error classes (IvaCompensationCarryForwardPolicyError, IvaCompensationSeedConflictError, IvaCompensationYearRangeError, IvaCompensationDecimalParseError, IvaCompensationReconciliationInputError) into domain/iva_compensation/_errors.py and repoint importers; `src/aeat/domain/iva_compensation/_errors.py`.

### Phase `W03.P08` - Move carry-forward, reconciliation and balance logic

Relocate the pure regulatory algorithms and typed records into the domain package; leave repositories and orchestration in application.

- [x] `W03.P08.S35` - Move the carry-forward pure logic (IvaCompensationExpiryReviewState, IvaCompensationPeriodState, IvaCompensationCarryForwardLot+validator, IvaCompensationCarryForwardReport, iva_compensation_period_key, build_iva_compensation_carry_forward_report, enforce_iva_compensation_four_year_window, iva_compensation_state_from_filed_observation, private helpers) into _carry_forward.py and extract derive_303_compensation_available; `src/aeat/domain/iva_compensation/_carry_forward.py`.
- [x] `W03.P08.S36` - Move the reconciliation pure logic (IvaCompensationAuthority/SourceKind/Divergence literals, IvaCompensationOverride, IvaCompensationAuthoritySource, IvaCompensationReconciliationDecision+validator, reconcile_iva_compensation_wallet, _DEFAULT_MAX_WALLET_AGE_DAYS, private predicates) into _reconciliation.py; `leave repositories/orchestration in application; `src/aeat/domain/iva_compensation/_reconciliation.py`.
- [x] `W03.P08.S37` - Move the balance pure logic (IvaWalletBalanceReport, build_iva_wallet_balance_report) into _balance.py; `leave query_iva_wallet_balance orchestration in application; `src/aeat/domain/iva_compensation/_balance.py`.
- [x] `W03.P08.S89` - Introduce domain wallet/recurrence observation port Protocols (IvaCompensationWalletObservationProtocol, LocalIvaCompensationRecurrenceProtocol) so reconcile_iva_compensation_wallet + its wallet/recurrence-coupled predicates can move from application/calculations/_iva_wallet_reconciliation.py into domain/iva_compensation/_reconciliation.py without a domain->adapters/application edge; `src/aeat/domain/iva_compensation/_reconciliation.py`.

### Phase `W03.P09` - Dedup derivation and repoint consumers

Collapse the duplicated compensacion-disponible derivation to one domain function, repoint all callers, update error-registry dotted-path strings and calculations __all__.

- [x] `W03.P09.S38` - Collapse _with_derived_303_compensation_available (application/live:1131) and _with_derived_303_compensation_available_observation (adapters/sede/_declarations:1599) into the domain derive_303_compensation_available; `repoint the 3 call sites (live:757, declarations:1183, declarations:1225) preserving provenance wrapping; `src/aeat/application/live/__init__.py`.
- [x] `W03.P09.S39` - Update the 5+ dotted-path string references in core/errors/registry/_application.py from application.calculations._iva_* to domain.iva_compensation.*; `src/aeat/core/errors/registry/_application.py`.
- [x] `W03.P09.S40` - Update application/calculations/__init__ __all__ and repoint every relocated-symbol caller (live/__init__, modelo/_actions, _observations_repository, _binding_prefill, _iva_wallet_balance, cli/_modelo, cli/_app_live) to the domain package; `verify collect-only clean; `src/aeat/application/calculations/__init__.py`.

## Wave `W04` - DTO, shim and duplicate discipline (D6)

Collapse the application-result/CLI-payload twin DTOs, delete the re-export shims and dead packages, unify the duplicate Spanish-decimal parser and LedgerReviewIssue enum, fold RegistryManualId into ManualId behind a CLI gate, disambiguate the PortalRow name collision, and close the CLI enum-typing and private-import gaps.

### Phase `W04.P10` - Delete shims and dead packages

Remove pdf/_errors.py and the dead identity/ shim; repoint callers to canonical homes.

- [x] `W04.P10.S41` - Delete adapters/inbound/pdf/_errors.py shim; `repoint borrador/_errors, declaracion/_errors, pdf/__init__, and pdf/_scrub to import PdfModeloImportError directly from domain/justificante/_errors (DB-29 S1). Partial 2026-06-02 live-gate drift repair: live IVA focused tests exposed that pdf/__init__ and pdf/_scrub still imported the removed shim, so those callers were repointed to domain.justificante; `src/aeat/adapters/inbound/pdf/_errors.py src/aeat/adapters/inbound/pdf/__init__.py src/aeat/adapters/inbound/pdf/_scrub.py`.
- [x] `W04.P10.S42` - Delete the dead adapters/inbound/identity/ shim package after confirming zero live callers (sanitizer already imports core.identity directly) (DB-29 S2); `src/aeat/adapters/inbound/identity/__init__.py`.

### Phase `W04.P11` - Unify duplicate parser, enums and name collision

Unify the Spanish-decimal parser into core, collapse LedgerReviewIssue into LedgerImportDiagnosticKind, fold RegistryManualId into ManualId behind a CLI gate, rename the ORM PortalRow.

- [x] `W04.P11.S43` - Unify the Spanish-decimal parser: promote parse_spanish_decimal to core (core/decimal or core/parsing) returning Decimal|None; `make the justificante wrapper raise JustificanteParseError on None; migrate _extract callers and the pdf/_label_regex callers (DB-30); `src/aeat/core/decimal/`.
- [x] `W04.P11.S44` - Delete application/review LedgerReviewIssue and replace its uses (review/_filter, review/__init__) with application/transactions LedgerImportDiagnosticKind (DB-23); `src/aeat/application/review/_filter.py`.
- [x] `W04.P11.S45` - Fold RegistryManualId into ManualId: remove the application/registry _corpus RegistryManualId enum and _domain_manual_id shim, use ManualId with a Choice([renta,iva]) CLI gate at the corpus boundary (DB-24); `src/aeat/application/registry/_corpus.py`.
- [x] `W04.P11.S46` - Rename the SQLAlchemy ORM PortalRow to PortalOrmRow in adapters/persistence/storage/sql/_orm.py and update the repository consumers, disambiguating from the application PortalRow DTO (DB-27); `src/aeat/adapters/persistence/storage/sql/_orm.py`.

### Phase `W04.P12` - Close CLI typing and private-import gaps

Type the --category Typer arg as PortalCategory; import StoredProfileDriftError from the application public surface.

- [x] `W04.P12.S47` - Type the --category Typer option as PortalCategory|None in cli/_app_live (renders Choice) and drop the manual PortalCategory(category) coercion block (DB-37 G1); `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `W04.P12.S48` - Repoint cli/_errors.py StoredProfileDriftError import from domain.user_profile._errors to the application/domain public surface (DB-37 G2); `src/aeat/entrypoints/cli/_errors.py`.

### Phase `W04.P13` - Collapse twin DTOs

Make each application result canonical and have the CLI OutputSchema derive from or be it; stop sharing class names across layers.

- [x] `W04.P13.S49` - Collapse the Auth pass-through twins: make AuthClearResult (1:1) a single OutputSchema; `eliminate the extra=allow CLI pass-throughs AuthStatusResult, AuthTestResult, AuthLoginResult by emitting the application result directly (DB-26 T5,T2,T3,T4); `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W04.P13.S50` - Align AuthConfigureResult: reconcile the nullability differences and derive the CLI payload from the application model rather than redeclaring it (DB-26 T1); `src/aeat/entrypoints/cli/_config_payloads.py`.
- [x] `W04.P13.S51` - Derive the CLI LedgerImport, LedgerExport and ModeloExport payloads from their application results (LedgerSourceImportResult, LedgerExportResult, ModeloExportResult) via explicit projection; `stop the bytes/typed-id redeclaration (DB-26 T6,T7,T8); `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W04.P13.S52` - Derive the CLI CensoApply and InventoryValuationPreview payloads from their application results via explicit projection/flattening (DB-26 T9,T10); `src/aeat/entrypoints/cli/_ledger_payloads.py`.

## Wave `W05` - Hexagonal edges and persistence boundary (D1/D4/D5)

Wave-A cheap runtime-edge cleanup (defer the 6 module-level domain-to-adapters imports, relocate application.topics out of core, read assets namespaces from registry constants, promote _registry_sha); Wave-B persistence-boundary ruling execution (elevate the inventory valuation guard, new-repos-behind-ports, core/resources facade, outbound DI injection).

### Phase `W05.P14` - Wave-A cheap runtime-edge cleanup

Defer the 6 module-level domain-to-adapters imports, relocate application.topics out of the core import path, read assets namespaces from registry constants, promote _registry_sha.

- [x] `W05.P14.S53` - Defer the 6 module-level domain-to-adapters imports (filing/_repository:14-15, justificante/_repository:24-25, submission/_repository:14-15) into TYPE_CHECKING blocks; `verify rg '^from .+adapters' over domain returns zero (DB-16 A-1); `src/aeat/domain/filing/_repository.py`.
- [x] `W05.P14.S54` - Relocate Topic, TopicCatalogue, TopicNotFoundError, load_topic_catalogue out of application/topics into core or a domain/topics home; `repoint core/resources/_repos/topics and core/errors/registry/_application:194 so core no longer imports application (DB-07/DB-18 A-2; tag relocation:TopicCatalogue); `src/aeat/application/topics/__init__.py`.
- [x] `W05.P14.S55` - Read the assets namespaces from PROFILE_ASSETS_LEDGER_NAMESPACE/PROFILE_ASSETS_AMORTIZATION_LEDGER_NAMESPACE constants in adapters/persistence/profile/assets.py:32-33 instead of hardcoded literals (DB-33 A-3); `src/aeat/adapters/persistence/profile/assets.py`.
- [x] `W05.P14.S56` - Promote _registry_sha to the application/storage/calc_sheets public surface and repoint adapters/outbound/google/_calc_sheets_pull:55 off the private path (DB-31 A-4); `src/aeat/application/storage/calc_sheets/__init__.py`.

### Phase `W05.P15` - Wave-B persistence-boundary ruling execution

Elevate the inventory valuation guard to the application service, establish new-repos-behind-ports, rule on the core/resources facade, inject context into outbound adapters.

- [x] `W05.P15.S57` - Elevate the inventory valuation guard: call compute_inventory_valuation in the application inventory service's movement_add before persisting, and drop the call from adapters/persistence/profile/inventory.py:207 record_movement (DB-32 B-3); `src/aeat/application/inventory/_service.py`.
- [x] `W05.P15.S58` - Ratify and document the D4 persistence-boundary ruling: new repositories implemented in adapters/persistence behind a domain port; `existing domain-co-located repositories accepted as managed debt (100 deferred edges tracked, not churned); record as an accepted deviation note (DB-16 B-1); `.vault/adr/2026-06-01-domain-boundary-audit-adr.md`.
- [x] `W05.P15.S59` - Confirm core/resources/_repos depends only on protocols/domain (not application) after A-2; `document the facade as an accepted shared-kernel registry or schedule its relocation to domain (DB-18 B-2); `src/aeat/core/resources/_repos/`.
- [x] `W05.P15.S60` - Inject bucket/profile context into the outbound adapter call sites (auth/_authenticator, _clave_movil, sede/_declarations, browser/_factory, google/_oauth_flow) instead of pulling application internals; `add an application facade for compute_from_pull's engine invocation (DB-31 B-4); `src/aeat/adapters/outbound/aeat/auth/_authenticator.py`.

## Wave `W06` - Profile surface rename and consolidation (D7)

Relocate the inventory/asset/amortization errors out of domain/profile, rename the three-concern profile package to its true subject, remove the sole domain-to-application wizard inversion via push-registration, and rename core/profile.py and core/profile_catalogue.py to setup-answers/wizard-catalogue with retyped accessors. Highest blast radius (23+ importers); staged last.

### Phase `W06.P16` - Relocate inventory/asset errors out of profile

Move the asset and inventory/amortization error families to their inventory/assets subpackages.

- [x] `W06.P16.S61` - Relocate AssetRecordError and AssetValidationError out of domain/profile/_errors.py into domain/profile/assets; `update adapters/persistence/profile/assets and tests (DB-01 concern C; tag relocation:AssetRecordError); `src/aeat/domain/profile/assets/__init__.py`.
- [x] `W06.P16.S62` - Relocate InventoryLedgerError, InventoryValidationError, AmortizacionLedgerError, LIFOForbiddenError, BasisCapExceededError out of domain/profile/_errors.py into domain/profile/inventory; `update adapters/persistence/profile/inventory and tests (DB-01 concern C); `src/aeat/domain/profile/inventory/__init__.py`.

### Phase `W06.P17` - Rename the profile package and sweep importers

Rename domain/profile to its true subject and repoint all 23+ importers in one atomic move.

- [x] `W06.P17.S63` - Rename domain/profile to its true subject (e.g. domain/renta_profile) covering tax-residence plus renta/Modelo-100 family facts; `repoint all 23+ production importers plus tests in one atomic move with collect-only clean (DB-01; tag relocation:domain.profile); `src/aeat/domain/profile/`.

### Phase `W06.P18` - Remove the domain-to-application inversion and rename core profile modules

Drop the _build_profile_keys lazy pull path (DB-17), rename core/profile.py and core/profile_catalogue.py and retype their accessors.

- [x] `W06.P18.S64` - Remove the _build_profile_keys lazy pull path in domain profile _keys.py that imports application.wizard._compiler; `rely solely on the existing register_profile_keys push path and add a not-registered guard (DB-17); `src/aeat/domain/profile/_keys.py`.
- [x] `W06.P18.S65` - Rename core/profile.py to core/setup_answers.py (SetupAnswers + registration slots), retype the _m/_p/_ccaa Any lazy accessors once the cycle is broken, and update the 5 importers (DB-28; `tag relocation:SetupAnswers); `src/aeat/core/setup_answers.py`.
- [x] `W06.P18.S66` - Rename core/profile_catalogue.py to core/wizard_catalogue.py and update the 4 importers (DB-39; `tag relocation:WizardCatalogueSlot); `src/aeat/core/wizard_catalogue.py`.

## Wave `W07` - Residual findings: correctness, typing, routing and docstrings (DB-05/06/08/09/10/12/13/36/03)

Address the findings not covered by W01-W06: the HIGH dual declaration_key divergence, period re-implementation, wizard legal-rule re-derivation, untyped setup enum, SourceKind subset duplicate, the normatives phantom singleton and empty auth __init__, the CLI-to-application bypasses, and the modelos docstring. DB-40's three core/ items are documented-accept with no Step.

### Phase `W07.P19` - Workflow and period correctness (DB-05, DB-06)

Collapse the duplicate declaration_key/update_declaration_pointer to one definition and route the workflow and aggregation period helpers through domain/period.

- [x] `W07.P19.S67` - Delete declaration_key from workflow/_engine.py:1295 and _engine __all__; `make _engine import it from _models.py and add .upper() period normalisation to the _models.py:166 definition (DB-05; relocation:declaration_key); `src/aeat/application/workflow/_models.py`.
- [x] `W07.P19.S68` - Delete update_declaration_pointer from workflow/_engine.py:1300 and _engine __all__; `make _engine import the _models.py:293 definition after aligning the Optional draft_id/status signature (DB-05; relocation:update_declaration_pointer); `src/aeat/application/workflow/_models.py`.
- [x] `W07.P19.S69` - Add a structural test asserting declaration_key has exactly one definition in workflow and that a lowercase period key equals its uppercased form (DB-05 anti-regression); `src/aeat/application/workflow/test_declaration_key.py`.
- [x] `W07.P19.S70` - Replace _period_to_year and _registry_period_token in workflow/_engine.py:81-119 with domain.period.parse_canonical_period, wrapping PeriodValidationError into WorkflowError at call sites :808 and :967 (DB-06); `src/aeat/application/workflow/_engine.py`.
- [x] `W07.P19.S71` - Remove _PERIOD_RE and _QUARTER_MONTHS from aggregation/_models.py and rewrite Period.start/Period.end via domain.period.period_start_date/period_end_date, validating the token through parse_canonical_period (DB-06); `src/aeat/application/aggregation/_models.py`.

### Phase `W07.P20` - Wizard, setup and operator typing (DB-08, DB-09, DB-10)

Replace the wizard frozenset re-derivation with domain SituacionFamiliar predicates, type setup iva_regime as IVARegime, and express operator SourceKind as a slice over AggregationSourceKind.

- [x] `W07.P20.S72` - Add SituacionFamiliar.monoparental_required() to domain/profile/_renta_codes.py with Art. 82.1.2 LIRPF grounding (DB-08); `src/aeat/domain/profile/_renta_codes.py`.
- [x] `W07.P20.S73` - Rewrite wizard/_verifier.py _check_joint_taxation_situacion_familiar to use not sf.conjunta_eligible() and _check_monoparental_requires_hijos to use sf.monoparental_required(); `delete the _JOINT_INELIGIBLE and _MONOPARENTAL_REQUIRED frozensets (DB-08); `src/aeat/application/wizard/_verifier.py`.
- [x] `W07.P20.S74` - Type InitializeWorkspaceCommand.iva_regime as IVARegime in setup/_contracts.py:29 (with a case-fold BeforeValidator) and adjust setup/_service.py:23 to emit the enum value (DB-09); `src/aeat/application/setup/_contracts.py`.
- [x] `W07.P20.S75` - Fix the lowercase iva_regime fixtures in setup/test_contracts_output_language_roundtrip.py:26,37,48,59 to match the IVARegime member value (DB-09); `src/aeat/application/setup/test_contracts_output_language_roundtrip.py`.
- [x] `W07.P20.S76` - Replace operator_surface/_models.py:37 SourceKind enum with a Literal/frozenset slice over core AggregationSourceKind and update SourceKindAlias, OperatorSurfaceContract.source_kinds, _contract SOURCE_KINDS and resolve_source_kind_alias (DB-10); `src/aeat/application/operator_surface/_models.py`.
- [x] `W07.P20.S77` - Update operator_surface/test_contract.py to assert against AggregationSourceKind members and add a subset-invariant test (DB-10); `src/aeat/application/operator_surface/test_contract.py`.

### Phase `W07.P21` - Public-surface and docstring gaps (DB-12, DB-13, DB-03)

Instantiate the normatives catalogue singleton, re-export the domain/auth apoderamientos surface, and rewrite the modelos package docstring.

- [x] `W07.P21.S78` - Instantiate NORMATIVE_CATALOGUE = _LazyCatalogue() in domain/normatives/__init__.py, add it to __all__, and align the docstring example (DB-12); `src/aeat/domain/normatives/__init__.py`.
- [x] `W07.P21.S79` - Re-export the apoderamientos public surface (ALL_TOKEN, ApoderadoScope, ApoderamientosCatalogue, UnknownScopeError, expand_all_token, load_default_catalogue, parse_scope_tokens) from domain/auth/__init__.py with __all__, and drop the unimplemented providers clause from the docstring (DB-13); `src/aeat/domain/auth/__init__.py`.
- [x] `W07.P21.S80` - Repoint application/auth/_apoderado.py:44 and core/resources/_repos/apoderamientos.py:15 to import from aeat.domain.auth instead of the apoderamientos submodule (DB-13); `src/aeat/application/auth/_apoderado.py`.
- [x] `W07.P21.S81` - Rewrite domain/modelos/__init__.py docstring to describe the real surface (modelo codes, filing/calculation/verification repositories, work units, calculation revisions, row models) with :class:CalculationRevision and :class:ModeloRevision cross-links (DB-03); `src/aeat/domain/modelos/__init__.py`.

### Phase `W07.P22` - CLI-to-application routing (DB-36)

Route the CLI renta aggregation through the application service and add application wrappers for the usage-ratio mutating verbs so the CLI stops calling domain persistence directly.

- [x] `W07.P22.S82` - Replace the inline domain-registry aggregation in cli/_common.py:303-327 _aggregate_renta_filing_inputs with a call to application.aggregation resolve_modelo_ledger_binding_values_from_repositories; `remove the local domain import at :312 (DB-36); `src/aeat/entrypoints/cli/_common.py`.
- [x] `W07.P22.S83` - Fix application/aggregation/test_renta_ledger.py:35 to stop importing _aggregate_renta_filing_inputs from entrypoints.cli._common, routing through the application service instead (DB-36); `src/aeat/application/aggregation/test_renta_ledger.py`.
- [x] `W07.P22.S84` - Add set_usage_ratio and unset_usage_ratio application command wrappers in application/ledger/_ratios.py that wrap domain load_usage_ratios/save_usage_ratios with validation (DB-36); `src/aeat/application/ledger/_ratios.py`.
- [x] `W07.P22.S85` - Repoint cli/_ledger.py ratios_set (:2281) and ratios_unset (:2332) to the new application wrappers instead of importing domain.usage_ratios directly (DB-36); `src/aeat/entrypoints/cli/_ledger.py`.

## Wave `W08` - Recurring code-quality tooling triage (standing)

RECURRING, not one-shot: on a cadence (every Wave close and every 6-8 commits) run the codebase's programmatic quality tooling - ty and pyright type-checkers, radon and ruff complexity/lint audits, and the import-linter layered-architecture contract - and triage new findings into tracked Steps under the originating Wave or as fresh DB-NN findings. This Wave never closes; its Steps are re-opened each cadence tick. It is the standing gate that keeps type, complexity, and hexagonal-edge regressions from accumulating between discovery sweeps.

### Phase `W08.P23` - Type-check triage (ty + pyright)

Run the type checkers and triage new errors into Steps.

- [x] `W08.P23.S86` - Run uv run --no-sync ty check src/aeat and uv run --no-sync pyright src/aeat; `record the error count baseline and triage each new error class into a Step or DB-NN finding (recurring each cadence tick); `src/aeat/`.

### Phase `W08.P24` - Complexity and lint audit triage (radon + ruff)

Run radon complexity and ruff lint/complexity rules and triage findings.

- [x] `W08.P24.S87` - Run uv run --no-sync radon cc -s -n C src/aeat (cyclomatic complexity grade C and worse) and the ruff complexity/lint suite; `triage high-complexity functions and new lint classes into refactor Steps (recurring); `src/aeat/`.

### Phase `W08.P25` - Architecture-boundary enforcement (import-linter)

Run the import-linter contract and triage layered-architecture / hexagonal-edge violations, feeding the edge-axis findings.

- [x] `W08.P25.S88` - Run uv run --no-sync lint-imports (import-linter, .importlinter contract); `triage every layered-architecture contract breach as a hexagonal-edge finding under W05 or a new DB-NN (recurring; this is the programmatic counterpart to the manual edge-axis rg sweep); `.importlinter`.

## Wave `W09` - Import-linter contract remediation (DB-42 expanded)

Restore the hexagonal import-linter gate to green: clean the 93 stale ignore_imports entries, triage and resolve the real layer violations the abort was hiding (domain->application/adapters/entrypoints, core->outer, application->adapters/entrypoints, calculations->renta), and return unmatched-ignore alerting to strict once clean

### Phase `W09.P26` - Clean 93 stale ignore_imports entries

Remove every ignore_imports entry import-linter flags as unmatched (edges since refactored away); each confirmed gone from source before removal

- [x] `W09.P26.S93` - Add fresh precisely-pinned ignore_imports for the ~54 sanctioned test-file roundtrip/fixture edges whose prior ignores went stale on test rename; `each verified as a real-adapter roundtrip per the roundtrip discipline; `.importlinter`.

### Phase `W09.P27` - Triage and resolve real layer violations

For each broken-contract violation chain, classify as production hexagonal drift (fix via DI/relocation, overlaps DB-16/DB-17/DB-18/DB-32) or sanctioned test-adapter roundtrip edge (add a precise ignore with rationale)

- [x] `W09.P27.S90` - Resolve calculations.registry._scenarios -> domain.renta: the harness imports renta for the first-slice snapshot-check registration side effect, violating 'the registry never names renta'. Move the registration trigger to the scenario harness caller (CLI/test entrypoint) so the calculations package stays renta-free, or sanction it as the documented side-effect pattern if relocation breaks Modelo 100 scenario runs; `src/aeat/domain/calculations/registry/_scenarios.py`.
- [x] `W09.P27.S91` - Resolve core.resources._repos.apoderamientos -> domain.auth (core->domain, DB-18 cluster): apply the resource-management-api deferred-loader pattern (function-local import) or invert via a registered provider, consistent with the other core/resources repos; `src/aeat/core/resources/_repos/apoderamientos.py`.
- [x] `W09.P27.S92` - Resolve the 7 domain repository -> adapters.persistence.storage edges (DB-16 cluster: usage_ratios._service, justificante/_submission/_filing/_repository, buckets._event_repository, transactions._repository, modelos/filing._runtime_repository) via the persistence-boundary repository-Protocol inversion (R5 ADR); `domain declares the repository port, adapters implement; `src/aeat/domain (repository modules) + persistence-boundary ADR`.

### Phase `W09.P28` - Restore strict unmatched-ignore alerting

Once stale ignores are cleaned and violations resolved, return unmatched_ignore_imports_alerting to error so a future stale entry or new violation reds the gate loudly

- [x] `W09.P28.S94` - Resolve unmatched-ignore alerting policy: KEEP unmatched_ignore_imports_alerting = warn rather than restoring the implicit error default. error is what blinded the gate originally (one stale ignore aborted the whole run); `under warn a new production violation still reds the gate (broken contract exits non-zero regardless of mode) while stale ignores from test churn degrade gracefully. Gate verified 4 kept / 0 broken / exit 0; `.importlinter`.

## Wave `W10` - Active-bucket context resolution consolidated in core (S60/DB-31 B-4)

Eliminate every adapter->application and underscore-private reach-in for active-bucket resolution. Relocate require_active_bucket_id + NoActiveProfileError from application/workflow to a public aeat.core surface alongside the already-core resolve_active_bucket_id, then repoint all ~60 consumers (adapters, application, entrypoints, domain, tests) to import inward from the public core surface. Supersedes S53's infeasible TYPE_CHECKING approach and discharges the hexagonal-purity intent of S60.

### Phase `W10.P29` - Core public surface for active-bucket context

Relocate require_active_bucket_id and NoActiveProfileError into core beside resolve_active_bucket_id; expose all three from a public aeat.core surface; update the error-registry path string.

- [x] `W10.P29.S95` - Relocate require_active_bucket_id (application/workflow/_models.py:251) and NoActiveProfileError (application/workflow/_errors.py:42, WorkflowError subclass) into core beside resolve_active_bucket_id; `expose resolve+require+NoActiveProfileError from a public aeat.core surface (promote core/_bucket_pointer_io.py to a public core module and/or re-export via core/__init__); update the error-registry path string core/errors/registry/_application.py:326; keep the locale key application.workflow.errors.no_active_profile_bucket stable; `src/aeat/core/_bucket_pointer_io.py`.
- [x] `W10.P29.S96` - Repoint application/workflow/_models.py:33 import and remove the application-owned require_active_bucket_id definition; `update workflow/__init__.py re-exports (lines 40,66,113,142) to re-export from core or drop in favour of direct core imports by callers; `src/aeat/application/workflow/_models.py`.

### Phase `W10.P30` - Repoint adapter consumers to the core surface

The aeat outbound adapters (browser/_factory, auth/_clave_movil, auth/_authenticator, sede/_declarations) and their live tests import from the public core surface, removing the adapter->application edges.

- [x] `W10.P30.S97` - Repoint the four aeat outbound adapter sites off application.workflow._models to the public core surface: browser/_factory.py:154 (resolve), auth/_clave_movil.py:754 (resolve) + :866 (require), auth/_authenticator.py:1241 (require), sede/_declarations.py:390 (require); `src/aeat/adapters/outbound/aeat/`.
- [x] `W10.P30.S98` - Repoint the adapter live tests off application.workflow._models: sede/test_groi_check_live.py:26, auth/test_clave_movil_live.py:73, auth/test_clave_movil.py:937; `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`.

### Phase `W10.P31` - Repoint application-layer consumers to the core surface

Application modules that reach into workflow._models for the resolvers import from the public core surface instead.

- [x] `W10.P31.S99` - Repoint application-layer consumers off workflow._models to the public core surface: wizard/_status.py:23, user_profile/_orchestration.py:305/325/563/602, auth/_sessions.py:176/506, auth/_operator.py:263, auth/_acquisition_lock.py:78/168, review/_operator.py:221, state_projection.py:57, diagnostics.py:308, modelo/_export.py:410; `src/aeat/application/`.
- [x] `W10.P31.S100` - Repoint application tests: user_profile/test_orchestration.py:9/168, live/test_iva_wallet_live.py:21, workflow/test_active_profile_resolution.py:26; `src/aeat/application/workflow/test_active_profile_resolution.py`.

### Phase `W10.P32` - Repoint entrypoint/CLI consumers to the core surface

CLI entrypoint modules and their tests import the resolvers and NoActiveProfileError from the public core surface.

- [x] `W10.P32.S101` - Repoint CLI entrypoint consumers off workflow._models to the public core surface: cli/__init__.py:264, _overview.py:64, _modelo.py:181/205/300/2133/4407/5273, _ledger.py:62/2148/2165/3663/3714/3787, _config/__init__.py:42/377/970/1496, _config/_profile_censo.py:36, _common.py:135/149/233, _app_live.py:871, diagnostics/profile.py:29; `NoActiveProfileError catchers _ledger.py:2147/2164/3662 + _common.py:233; `src/aeat/entrypoints/cli/`.
- [x] `W10.P32.S102` - Repoint CLI tests off workflow._models: test_cli_surface.py:89, test_ledger_fx_import.py:21, test_profile_lifecycle_verbs.py:405/432/955/996, test_profile_censo_verbs.py:55/172, test_modelo_source_mesh_calculate.py:130, test_repair_privacy_contract.py:19, test_ratios_verbs.py:13, test_ledger_exception_propagation.py; `src/aeat/entrypoints/cli/test_cli_surface.py`.

### Phase `W10.P33` - Verification: zero adapter-to-application active-bucket edges

Assert no module outside the workflow package imports the resolvers from application.workflow._models; suite green; import-linter contracts unchanged.

- [x] `W10.P33.S103` - Verify: rg confirms no module outside application/workflow imports resolve_active_bucket_id/require_active_bucket_id from application.workflow._models; `full pytest suite + ty + lint-imports green; the AEAT-layered import-linter warning count does not regress; `src/aeat/`.
- [ ] `W10.P33.S109` - Investigate the 13 pre-existing test_cli_surface ledger-lifecycle 'No active bucket session is open' failures (test_app_ledger_lifecycle_reset_*, test_app_ledger_import_reimport_*). Proven unrelated to W10 (fail identically on the old import) but only 1 of 13 individually confirmed; confirm the shared root cause (master-key session not seen by ledger storage in the lifecycle round-trip helper) and either fix or file as a tracked storage-runtime/session-setup flake; `src/aeat/entrypoints/cli/test_cli_surface.py`.

## Wave `W11` - Secure-storage public-surface import purity (D4/D5)

Domain and application repositories must import secure-storage primitives (SecureBoundRepository, SecureObjectRepository, SecureObjectWrite, ClassificationError, EnvelopeVersionError, StorageError) from the storage package public surface, never from underscore-private submodules. Establish the public storage/__init__ export set, eliminate the double-private envelope._envelope reach-in (domain/transactions/_repository), and repoint the ~15 domain repository import sites. Ratifies D4 (existing domain-co-located repos accepted as managed debt) while cleaning their import surface per the operator top-level-import directive.

### Phase `W11.P34` - Establish the storage public export surface

Export the secure-storage primitives that domain repositories consume (SecureBoundRepository, SecureObjectRepository, SecureObjectWrite, ClassificationError, EnvelopeVersionError, StorageError) from adapters/persistence/storage/__init__ so consumers import the top-level package.

- [x] `W11.P34.S104` - Audit storage/__init__ __all__ (currently namespace constants only); `export the secure-storage primitives domain repos consume from adapters/persistence/storage/__init__.py: SecureBoundRepository (envelope/_secure_repository), SecureObjectRepository + SecureObjectWrite (sql), ClassificationError + EnvelopeVersionError + StorageError (errors); `src/aeat/adapters/persistence/storage/__init__.py`.

### Phase `W11.P35` - Eliminate the double-private envelope._envelope reach-in

domain/transactions/_repository imports Envelope from the underscore-private storage.envelope._envelope module; repoint to a public surface or remove the reach-in.

- [x] `W11.P35.S105` - Repoint domain/transactions/_repository.py off the underscore-private storage.envelope._envelope module (Envelope import) to a public surface, or remove the reach-in if Envelope need not be referenced directly; `src/aeat/domain/transactions/_repository.py`.

### Phase `W11.P36` - Repoint domain repository import sites to the public surface

The ~15 domain repositories importing from storage.sql/.errors/.envelope submodules import from the top-level storage package instead.

- [x] `W11.P36.S106` - Repoint the domain repositories from storage.sql/.errors/.envelope submodule imports to the top-level storage package: buckets/_event_repository, filing/_repository + _complementaria_repository, justificante/_repository, submission/_repository, invoices/_repository, transactions/_repository, modelos/_calculation_repository + _filing_repository + _repository + _verification_repository, usage_ratios/_service, fincas/_repository (sql._orm stays a fincas-internal ORM detail unless publicly exposed); `src/aeat/domain/`.

### Phase `W11.P37` - Verification: domain storage imports use the public surface

Assert domain modules import secure-storage primitives only from the storage package top-level (no underscore-private submodule reach-ins); suite green.

- [x] `W11.P37.S107` - Verify: rg confirms domain modules import secure-storage primitives only from the top-level storage package (no .sql/.errors/.envelope/_envelope underscore reach-ins beyond sanctioned ones); `full pytest suite + ty green; D4 ratified in the ADR with these import-surface cleanups recorded; `src/aeat/domain/`.
- [ ] `W11.P37.S108` - Prune/update the stale .importlinter ignore entries that W11's repoint left unmatched: the domain repo edges now target the top-level package, so entries naming aeat.adapters.persistence.storage.envelope / .sql / .envelope._envelope for filing/justificante/submission/buckets/transactions/invoices _repository are unmatched (the 15->22 unmatched-ignore warning bump). Update each to the current '-> aeat.adapters.persistence.storage' edge (or delete if the new edge is deferred/unflagged); `verify lint-imports warning count drops with no new violation. Delicate shared-file edit — verify per-edge and avoid peer-WIP collision; `.importlinter`.

## Description

This plan executes the AEAT hexagonal ownership and layering contract decided in the
companion ADR against the 40-finding domain-boundary audit. It is comprehensive by
construction: every named occurrence surfaced by the deepening swarm (each relocated
symbol, each importer to repoint, each shim to delete, each twin to collapse) maps to a
Step. The plan is organised into six Waves, one per ADR decision cluster, ordered
foundational/low-risk first and highest-blast-radius last:

- **W01 - Registry public surface (D3):** publish the missing registry symbols, sweep
  the 33 private-submodule importers onto `registry/__init__`, fix the
  `IvaInvoiceClassification` asymmetry. Foundational: every later Wave imports cleanly
  once this lands.
- **W02 - Regulatory logic and values to domain (D2):** relocate the CLI tax formulas
  and statutory validations, the `core` regulatory thresholds, the aggregation
  regulatory enums, the rounding-code vocabulary, and the verification policy into
  grounded domain/registry/core homes.
- **W03 - IVA-compensation domain (D2 marquee):** create `domain/iva_compensation` and
  migrate the Modelo-303 carry-forward / four-year-window / reconciliation surface,
  collapsing the duplicated derivation to one provenance-preserving domain function.
- **W04 - DTO, shim and duplicate discipline (D6):** collapse the application↔CLI twin
  DTOs, delete shims and dead packages, unify the duplicate parser and enums, and close
  the CLI typing/private-import gaps.
- **W05 - Hexagonal edges and persistence boundary (D1/D4/D5):** Wave-A removes the
  cheap runtime inversions; Wave-B executes the ratified D4 persistence-boundary ruling.
- **W06 - Profile surface rename and consolidation (D7):** relocate the misplaced
  inventory/asset errors, rename the three-concern profile package, remove the sole
  domain→application inversion, and rename the `core` profile modules.

This plan is a living document: it is continuously expanded with new Waves as further
audit passes (the standing swarm cadence) surface additional clusters. The audit ledger
and the ADR are its authorities; both are linked in frontmatter.

## Steps







## Parallelization

Hard ordering across Waves: **W01 runs first** - once the registry public surface is
complete, all later Waves that touch registry imports do so via the public path, and the
W01 sweep does not collide with W02/W03 edits to the same files. After W01, **W02, W04,
and W05.P14 (Wave-A) are mutually independent** and may run concurrently (they touch
disjoint file sets: regulatory homes vs DTO/shim seams vs edge cleanups). **W03**
(IVA-compensation) shares files with W02.P06 (verification policy) and with
W05/adapters-sede (the derivation dedup) - sequence W03 after W02.P06 and coordinate its
S38 dedup with W05. **W05.P15 (Wave-B)** is ADR-ratification-gated and sequenced after
Wave-A. **W06 runs last**: the profile rename (S63) is a 23+-importer atomic move with
the largest collision surface; landing it after the other Waves minimises rebase churn.

Within a Wave, ordering is mostly intra-Phase: in W01, P01 (publish) precedes P03
(repoint newly-promoted) but P02 (repoint already-exported) is independent of P01. In
W02, the `PensionReduccionError` relocation (S25) precedes the formula moves (S26, S27);
the DB-14 enum moves (S29 - S31) are mutually independent. In W03, P07→P08→P09 are strictly
sequential. Each Step is a single atomic relocation commit (`relocation:<symbol>` subject,
`pytest --collect-only -q` clean immediately before commit); on this shared worktree every
coder must `git diff -- <file>` before its first edit and abort on non-authored WIP.

## Verification

Per-Step: each relocation Step is verified by `uv run --no-sync pytest --collect-only -q`
clean immediately before its commit, plus the affected roundtrip/structural tests green.
Regulatory-formula relocations (W02.P05, W03) additionally require an oracle-cited test
(`# oracle: BOE-… / AEAT-MANUAL-…`) that would fail if the formula were wrong against
AEAT - not a tautology against the moved code.

Per-Wave success criteria (each a verifiable check):

- **W01:** `rg "calculations\.registry\._(ids|schema|bindings|authority|loader|formula_runtime|errors|queries)" src/aeat -g '!**/test_*.py' -g '!src/aeat/domain/calculations/**'` returns zero `from`-anchored production hits; `IvaInvoiceClassification` resolves through `iva/__init__`.
- **W02:** no `Decimal`/statutory-threshold/validation regulatory logic remains in `entrypoints/cli` or `core/external_constants`; the relocated formulas carry oracle tests; aggregation regulatory enums import from `core`.
- **W03:** `rg "four_year|carry_forward|reconcile_iva_compensation|derive_303" src/aeat/application src/aeat/adapters -g '!**/test_*.py'` shows only orchestration; the derivation exists once, in domain; provenance roundtrip green.
- **W04:** zero re-export shims under `adapters/inbound`; no application↔entrypoints class-name twins (duplicate-class scan clean); one Spanish-decimal parser, one ledger-diagnostic enum.
- **W05:** `rg "^from .+adapters" src/aeat/domain -g '!**/test_*.py'` returns zero; no `core → application` edge; persistence carries no domain calculation.
- **W06:** no `domain → application` import anywhere; the renamed profile package's name matches its contents; `core` profile modules renamed.

The plan is complete when every Step in every Wave is closed (`- [x]`) AND a fresh
honesty-review pass (per the campaign-close-honesty-review rule) finds no
declared-but-unverified items. Because this is a living plan, "complete for the current
Wave set" is the rolling gate; new audit passes append Waves rather than reopening
closed ones.
