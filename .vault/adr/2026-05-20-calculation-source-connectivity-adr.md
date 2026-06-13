---
tags: ["#adr", "#calculation-source-connectivity"]
date: "2026-05-20"
modified: '2026-05-20'
related:
  - "[[2026-05-20-calculation-source-connectivity-research]]"
---

# `calculation-source-connectivity` adr: `canonical calculation source mesh` | (**status:** `accepted`)

## Problem Statement

AEAT currently has two coherent state islands: financial input domains and
modelo calculation domains. The ledger, invoice, inventory, profile, property,
and live-source subsystems can store or compute useful facts, while the modelo
engine only sees manual casilla inputs, caller binding overrides, and the
sources explicitly passed to the calculation call.

The immediate defect is that the operator CLI calculation path can bypass the
existing bucket-local ledger aggregation bridge. Classified ledger
transactions can be present in the active bucket, but `app modelo work
calculate` calls the lower-level calculation function directly and does not
resolve ledger-backed binding values by default.

The broader defect is architectural. Each new financial source currently needs
bespoke hand wiring to reach registry bindings. That makes all-zero outputs a
recurring failure mode for invoices, inventory, fincas, profile facts, prior
filings, and future source families.

## Considerations

The codebase already has useful primitives:
`TransactionCatalogueRepository` is bucket-scoped and secure; application
aggregation can project ledger rows to typed IVA and Renta observations;
registry binding resolvers consume typed observation shapes; calculation
revisions persist source transaction ids and typed casilla observations; and
bucket events provide an audit trail.

The existing bridge is too narrow as an operator contract. `calculate_modelo_revision_from_bucket_aggregation`
proves the bridge can work, but it is not the only public calculation path and
is not the path used by `app modelo work calculate`.

The registry already enumerates source kinds in `DataBindingDefinition`, but a
source kind in the registry is not the same as an enrolled application
resolver. A binding source must be backed by a deterministic application
adapter that knows how to read the active bucket, project source facts, produce
typed issues, and preserve provenance.

The application must retain the accepted hexagonal direction. Registry and
domain calculation code can define source selectors and observation protocols,
but storage, workflow, CLI, profile lifecycle, and source repository reads
belong in application adapters.

External grounding supports this shape: ports-and-adapters keeps application
logic independent from UI and persistence adapters; strict Pydantic boundary
models are appropriate for resolver contracts; Python Protocols allow the
registry to depend on observation shape instead of concrete source packages.

## Constraints

Application code must remain under `src/aeat/`.

Boundary payloads must be strict typed Pydantic v2 models, not bare
`dict[str, Any]`.

Calculation outputs must preserve legal refs, source refs, formula ids, source
object refs, binding ids, and typed observations. A flat casilla map may be
derived for readability, but it is not the authoritative contract.

The CLI root must remain `config` and `app`. The solution must improve the
existing `app modelo work calculate` behavior, not add a parallel root command.

Tests must use real behavior and real repositories. They must not use fakes,
mocks, stubs, monkeypatching shortcuts, skipped tests, xfail, or tautological
formula reimplementation.

Inventory and other source domains must not become calculation sources until
their persistence and provenance story is canonical enough for filing use.

## Grounded Code Discovery Inventory

This ADR is grounded in the following current code surfaces. The list is
intentionally repetitive: every affected site must be treated as a contract
surface when implementing the source mesh.

Application aggregation surface:

- `src/aeat/application/aggregation/_modelo_bindings.py` contains
  `ModeloLedgerBindingAggregation`,
  `resolve_modelo_ledger_binding_values_from_repositories`, and
  `aggregation_period_for_modelo`. This is the existing narrow bridge from
  bucket repositories into registry binding values.
- `src/aeat/application/aggregation/_iva_ledger.py` contains
  `IvaLedgerAggregationIssueReason`, `IvaLedgerAggregationIssue`,
  `ProrrataLedgerReference`, `IvaLedgerAggregation`,
  `aggregate_iva_ledger_observations_from_repositories`,
  `aggregate_iva_ledger_observations`, `_classify_iva_transaction`,
  `_flow_direction_for`, and `_iva_rate_kind_for`. This is the current ledger
  IVA source adapter.
- `src/aeat/application/aggregation/_renta_ledger.py` contains
  `RentaLedgerAggregationIssueReason`, `RentaLedgerAggregationIssue`,
  `_PurchaseInvoiceEvidencePayload`, `RentaLedgerExpenseAggregation`,
  `aggregate_renta_ledger_expenses_from_repositories`,
  `aggregate_renta_ledger_expenses`, `_classify_renta_transaction`,
  `_renta_direction_for`, `_business_amount`,
  `_purchase_invoice_evidence_payload`, and `_casilla_aggregation`. This is
  the current ledger Renta expense source adapter.
- `src/aeat/application/aggregation/_retenciones.py` contains
  `RetencionScheme`, `RetencionObservation`, `RetencionPerceptorRollup`,
  `RetencionesAggregation`, `aggregate_retenciones_111`,
  `aggregate_retenciones_115`, `aggregate_retenciones_123`,
  `aggregate_retenciones_180`, `aggregate_retenciones_190`, and
  `aggregate_retenciones_193`. This is aggregation logic, but it is not yet
  wired into the default bucket modelo calculation path.
- `src/aeat/application/aggregation/_counterpart.py` contains
  `OperationKind347`, `OperationKind349`, `CounterpartObservation`,
  `CounterpartRollup`, and `CounterpartAggregation`. This is the counterpart
  observation family for 347 and 349-style source cohorts.
- `src/aeat/application/aggregation/_foreign_assets.py` contains
  `ForeignAssetClass`, `ForeignAssetIngestObservation`,
  `ForeignAssetClassRollup`, and `ForeignAssetsAggregation`. This is the 720
  source family shape.
- `src/aeat/application/aggregation/_service.py` contains
  `AggregationSourceKind`, `PerModeloAggregationProvider`,
  `PerModeloAggregationProviderContract`, `PerModeloAggregationContract`,
  `PerModeloAggregationCommand`, `PerModeloAggregationResult`,
  `provider_for_modelo`, and `aggregate_per_modelo`. This is the closest
  existing generic aggregation service, but it is provider-grouped by modelo
  family rather than binding-source-driven for all registry sources.
- `src/aeat/application/aggregation/_registry_provider.py` contains
  `PerModeloRegistryBindingResolution` and counterpart registry binding
  resolution. This is a reusable pattern for turning source observations into
  registry binding values.
- `src/aeat/application/aggregation/_oss_ioss.py` contains
  `OssIossLedgerCandidate` and OSS/IOSS ledger binding aggregation. It must be
  enrolled as its own source resolver, not collapsed into domestic IVA.
- `src/aeat/application/aggregation/_models.py` contains `PeriodKind`,
  `Quarter`, `PeriodType`, `Period`, `CasillaProvenance`, and
  `CasillaAggregation`. Period normalization and provenance should be reused
  or centralized instead of duplicated in each source path.

Application modelo and filing surface:

- `src/aeat/application/modelo/_actions.py` contains
  `calculate_modelo_revision`, `_apply_iva_compensation_decision_binding`,
  `_taxpayer_nif_for_bucket`,
  `calculate_modelo_revision_from_bucket_aggregation`, `_ledger_binding_ids`,
  and `_reject_caller_overrides_of_ledger_bindings`. The hardcoded
  `ledger_iva_aggregation` and `ledger_renta_expense_aggregation` ownership
  check is the immediate place to generalize.
- `src/aeat/application/modelo/_borrador_binding.py` contains
  `Modelo100BorradorBindingCommand` and `Modelo100BorradorBindingResult`.
  Borrador is a calculation source and must participate through the same
  source ownership and provenance rules.
- `src/aeat/application/modelo/_export.py` contains `ModeloExportCommand` and
  `ModeloExportResult`. Export must consume row values and source-derived
  values after the mesh has resolved them.
- `src/aeat/application/modelo/_reconcile.py` contains
  `ModeloReconciliationCommand` and `ModeloReconciliationReport`.
  Reconciliation remains downstream from calculation and must not become a
  hidden source resolver.
- `src/aeat/application/filing/__init__.py` contains `build_draft`. The draft
  API accepts inputs and registry calculation values but does not itself read
  repositories for source-backed bindings.
- `src/aeat/application/filing/_review.py` contains
  `compute_current_approval_basis` and `approval_stale_reasons`. Approval
  staleness currently fingerprints only part of the source surface and must
  become source-mesh-aware.
- `src/aeat/application/filing/runtime.py` contains
  `ModeloOperatorProfile`, `RegistryCasillaSchema`, and runtime schema
  provider wiring. It is a runtime schema surface, not a source repository
  reader.

Registry calculation surface:

- `src/aeat/domain/calculations/registry/_schema.py` defines
  `DataBindingDefinition` source literals. Current committed source families
  include `ledger_iva_aggregation`, `ledger_renta_expense_aggregation`,
  `ledger_oss_aggregation`, `ledger_transaction`, `purchase_invoice_evidence`,
  `payable_invoice`, `collectible_invoice`, `profile`, `previous_filing`,
  `withholding`, `foreign_asset`, `manual_input`, `related_party_operation`,
  `atribucion_member`, and `refund_operation`.
- `src/aeat/domain/calculations/registry/_bindings.py` contains
  `CasillaObservation`, `RegistryModeloObservation`,
  `OracleModeloObservation`, `InvoiceObservation`,
  `InvoiceObservationRequirement`, `_InvoiceSelector`,
  `OssIossLedgerObservation`, `_OssIossLedgerSelector`,
  `IvaLedgerObservation`, `_IvaLedgerSelector`,
  `RentaExpenseObservationProtocol`, `_RentaLedgerExpenseSelector`,
  `CounterpartAggregationObservation`, `CounterpartObservationRequirement`,
  `WithholdingObservation`, `WithholdingObservationRequirement`,
  `_WithholdingSelector`, `RelatedPartyOperationObservation`,
  `_RelatedPartySelector`, `Modelo720RowObservation`, `_ForeignAssetSelector`,
  `AtributionMemberObservation`, `_AtributionSelector`,
  `RefundOperationObservation`, `_RefundSelector`, `_ProfileSelector`, and
  `_ManualInputSelector`.
- `src/aeat/domain/calculations/registry/_bindings.py` also contains
  `validate_ledger_iva_aggregation_binding_definition`,
  `resolve_ledger_iva_aggregation_binding_values`,
  `validate_ledger_renta_expense_aggregation_binding_definition`, and
  `resolve_ledger_renta_expense_aggregation_binding_values`. These are pure
  registry-side resolvers and must remain storage-free.
- `src/aeat/domain/calculations/registry/_validate.py` dispatches
  source-specific binding validators. Adding a source family requires registry
  validation here and application resolver enrollment separately.
- `src/aeat/domain/calculations/registry/_relations.py` contains
  relation-source requirements. Cross-model values are source dependencies and
  must be explicit in the source resolution envelope.
- `src/aeat/domain/calculations/registry/_queries.py` contains
  `RegistryQueryService` and report rows for model, casilla, binding, and
  formula discovery. The mesh should use the registry as the source of truth
  for required binding sources, not maintain a parallel static list.

Ledger and transaction surface:

- `src/aeat/domain/transactions/_models.py` contains `Transaction`,
  `TransactionCatalogue`, `BucketTransactionRef`,
  `ClassificationHistoryEntry`, `TransactionEvidenceProvenanceEntry`,
  `TransactionEditLineageEntry`, `TransactionLifecycleLineageEntry`, and
  `SplitLineage`. `Transaction` already carries `invoice_id`, `category_id`,
  `taxable_base`, `iva_rate`, `iva_amount`, `irpf_category`,
  `usage_ratio_id`, `prorrata_reference`, `purchase_invoice_evidence_id`, and
  `attachment_ids`.
- `src/aeat/domain/transactions/_enums.py` contains `TransactionDirection`,
  `BusinessClassification`, `TransactionLifecycleState`, and `SplitRole`.
  These enums are currently decisive for IVA and Renta aggregation.
- `src/aeat/domain/transactions/_repository.py` contains
  `TransactionCatalogueRepository`. It is bucket-scoped and source ids are
  unique only inside a bucket.
- `src/aeat/application/ledger/_actions.py` owns ledger mutation and guards
  finalized modelo dependencies through modelo source id checks. The mesh must
  preserve those dependency ids or expand them to typed source refs.
- `src/aeat/application/ledger/_models.py` contains
  `ManualLedgerTransactionCommand`, `ManualLedgerTransactionPatch`,
  `ManualLedgerTransactionResult`, `LedgerImportOperationResult`,
  `LedgerReviewRow`, `LedgerStatusReport`, `LedgerRemovalBlocker`,
  `LedgerTransactionRemovalReport`, `LedgerExportCommand`, and
  `LedgerExportResult`. CLI/application input can already carry IVA, IRPF,
  prorrata, evidence, and attachment fields.
- `src/aeat/application/ledger/_preflight.py` contains
  `LedgerPreflightIssueReason`, `LedgerPreflightIssue`, and
  `LedgerPreflightReport`. Preflight diagnostics should align with source mesh
  diagnostics instead of becoming a separate silent gate.
- `src/aeat/application/ledger/_ratios.py` contains `EligibleCategoryRow`,
  `RatiosValidationFinding`, `RatiosValidationReport`, and
  `RatiosCensoOverrideWarning`. Shared business expense ratios must flow into
  source resolution as explicit provenance, not only as transaction scalar
  values.

IVA domain surface:

- `src/aeat/domain/iva/_schema.py` contains `IvaCategory`, `EUMemberState`,
  `IvaRateKind`, and `IvaCitationSource`. Ledger IVA rate validation depends
  on these canonical rates and citations.
- `src/aeat/domain/iva/_flow.py` contains `IvaFlowDirection` and
  `IvaSettlementSide`. Current ledger mapping sends incoming rows to
  repercutido and outgoing rows to soportado.
- `src/aeat/domain/iva/_classification.py` contains `IvaTerritorialScope`,
  `InvoiceKind`, `CustomerTaxStatus`, and `TransactionKind`. Invoice-derived
  IVA source resolution should use this classification surface instead of
  reinterpreting invoice direction ad hoc.
- `src/aeat/domain/iva/_prorrata.py` contains `ProrrataRegime`,
  `ProrrataKind`, and `InputClassification`. Current ledger IVA aggregation
  records prorrata references but does not make the whole prorrata lifecycle a
  first-class source resolver.
- `src/aeat/domain/iva/_oss.py` contains `OssIossRegime`, `IossFilerRole`,
  `DeductionScope`, and `RegimePeriodicity`. OSS/IOSS must remain a distinct
  resolver and binding source.

Renta, category, and regional surface:

- `src/aeat/domain/renta/_ledger_expenses.py` contains
  `RentaExpenseDirection`, `RentaDeductibilityStatus`,
  `RentaInvoiceEvidenceStatus`, `RentaReconciliationStatus`,
  `RentaDeductibilityContext`, `RentaDeductibleExpenseFact`,
  `RentaDeductibilityResult`, `RentaDeductibleExpenseObservation`,
  `evaluate_renta_deductibility`, and
  `build_renta_deductible_expense_observation`.
- `src/aeat/domain/renta/_first_slice_routing.py` contains
  `FIRST_SLICE_EXPENSE_CASILLAS` and `expected_casilla_for_category`. Current
  Renta ledger binding coverage is first-slice only, not all deductible
  expense categories.
- `src/aeat/domain/renta/_substrate.py` contains `RentaIncomeType` and
  `EstimacionDirectaModalidad`. These are likely future inputs for full IRPF
  and Renta activity source routing.
- `src/aeat/domain/categories/_spending_category.py` contains
  `SpendingCategory` and `SpendingCategoryFamily`. This is the stable expense
  taxonomy for autonomo ledger categories.
- `src/aeat/domain/categories/_profile.py` contains
  `IvaDeductibilityHint` and `CategoryProfile`. Current profiles are year-keyed
  and do not carry CCAA-specific deductibility.
- `src/aeat/domain/categories/_proportionality.py` contains
  `CategoryCitationSource`, `CategoryCitation`, `ProportionalityKind`,
  `StatutoryCapPeriod`, `StatutoryCapVariant`, and `ProportionalityRule`.
  Shared business expense and statutory caps must stay here, not in registry
  formulas.
- `src/aeat/core/resources/_repos/category_profiles.py` contains
  `CategoryProfileRepository`. Its current key is the filing year. If expense
  categories differ by CCAA or foral regime, this repository and the
  `RentaDeductibilityContext` must become region-aware.
- `src/aeat/domain/profile/_ccaa.py` contains `CCAA`. CCAA is already bound
  into Modelo 100 profile facts, but it is not yet part of expense
  deductibility context.
- `src/aeat/domain/profile/__init__.py` contains `TaxResidenceProfile` and
  residence-change records. The source mesh should derive region context from
  profile source resolution, not duplicate profile parsing.

Invoice and evidence surface:

- `src/aeat/domain/invoices/_models.py` contains `InvoiceLine`, `Invoice`,
  and `InvoiceCatalogue`. `Invoice` carries `kind`, `base_total`, `iva_total`,
  `grand_total`, and `linked_transaction_ids`.
- `src/aeat/domain/invoices/_enums.py` contains `IvaRate` and
  `PaymentStatus`. Invoice-derived IVA and counterpart sources should preserve
  invoice rate and payment status evidence.
- `src/aeat/domain/invoices/_repository.py` contains
  `InvoiceCatalogueRepository`. Individual invoices carry bucket identity, so
  source resolvers must check bucket ownership when using this global
  catalogue.
- `src/aeat/domain/invoices/_service.py` contains
  `ReconciliationSuggestion`, `LinkInconsistency`, invoice link operations,
  reconciliation suggestion logic, and link consistency validation.
- `src/aeat/application/invoices/_linking.py` contains
  `InvoiceTransactionLinkResult` and `link_invoice_transaction_repositories`.
  This is the application-level bidirectional link between invoices and ledger
  transactions.
- `src/aeat/application/invoices/_reconciliation.py` contains
  `InvoiceReconciliationResult` and `reconcile_invoice_repositories`.
  Reconciliation can improve evidence links, but calculation must not depend
  on hidden reconciliation side effects.
- `src/aeat/application/invoices/_queries.py` contains `InvoiceListRow` and
  invoice list queries. These are read projections, not calculation source
  envelopes.
- `src/aeat/application/invoices/_projection.py` contains
  `InvoiceReviewProjection`, `InvoiceMatchRow`, and `InvoiceMatchProjection`.
  These are operator review projections and should not duplicate source
  resolution.
- `src/aeat/application/ledger/_evidence.py` contains
  `PurchaseInvoiceEvidence`, `PurchaseInvoiceEvidencePatch`,
  `PurchaseInvoiceEvidenceResult`, and `PurchaseInvoiceEvidenceService`.
  Purchase evidence is a separate application store and must be adapted into
  typed source observations before use in calculations.
- `src/aeat/application/ledger/_business_operation_invoice.py` contains
  `BusinessOperationInvoiceSourceKind`, `BusinessOperationInvoice`,
  `BusinessOperationInvoicePatch`, `_BusinessOperationInvoiceService`,
  `PayableInvoiceService`, and `CollectibleInvoiceService`. These payable and
  collectible invoice stores are parallel to the richer domain
  `InvoiceCatalogue` and must be normalized through source resolvers.

Fincas, property, and amortization surface:

- `src/aeat/domain/fincas/_models.py` contains `Finca`,
  `FincaRendimientoRecord`, `FincaGasto`, and
  `FincaAmortizacionLedgerEntry`.
- `src/aeat/domain/fincas/_repository.py` contains `FincaRepository`,
  `ArrendamientoRepository`, `FincaRendimientoRepository`,
  `FincaGastoRepository`, and `FincaAmortizacionLedgerRepository`.
- `src/aeat/domain/fincas/_aggregates.py` contains `FincaAttribution`,
  `ContractTierAttribution`, and `FincaAggregates`.
- `src/aeat/domain/fincas/_amortization_ledger.py` contains
  `AmortizationComputation`.
- `src/aeat/domain/fincas/_expense_rollup.py` contains
  `CarryForwardEntry` and `GastosForYear`.
- `src/aeat/domain/fincas/_enums.py` contains `UseType`,
  `ExpenseCategory`, and `ReduccionTier`.
- No current application source resolver was found that projects fincas,
  rental income, property expense, imputation, or amortization records into
  modelo binding values. That absence is an affected surface.

Inventory surface:

- `src/aeat/application/inventory/_service.py` contains
  `InventoryActividadSummary`, `InventoryMovementCommand`,
  `InventoryValuationPreview`, `InventoryLedgerResult`,
  `InventoryValuationPreviewResult`, and `InventoryService`.
- `src/aeat/domain/profile/inventory/__init__.py` contains `MovementKind` and
  `ValuationMethod`.
- Inventory is currently an application service over profile inventory
  structures and a ledgers-directory persistence path, not a secure
  repository-backed calculation source. It must not be enrolled until
  provenance and storage are canonical.

Secure storage, profile lifecycle, live, and workflow surface:

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py` contains
  `SecureObjectRepository`. This is the low-level encrypted object store.
- `src/aeat/adapters/persistence/storage/envelope/_secure_repository.py`
  contains `SecureBoundRepository`. This is the reusable typed encrypted
  repository pattern.
- `src/aeat/application/user_profile/_repository.py` contains
  `UserProfileLifecycleRepository` and `UserProfileSnapshotRepository`.
  Profile facts are source inputs and must be fingerprinted when used.
- `src/aeat/application/calculations/_observations_repository.py` contains
  `CalculationObservationRepository` and `IvaWalletDecisionRepository`.
  Prior observations and IVA wallet choices are source families.
- `src/aeat/application/calculations/_iva_compensation_history.py` contains
  `IvaCompensationHistoryRepository`. IVA compensation history is a source
  dependency for Modelo 303 chain behavior.
- `src/aeat/application/live/_borrador_100.py` contains
  `Borrador100SnapshotRepository`. Borrador values are source inputs for
  Modelo 100.
- `src/aeat/application/live/_censo.py` contains `CensoSnapshotRepository`.
  Censo snapshots can affect profile and obligation source context.
- `src/aeat/application/workflow/_persistence.py` contains
  `WorkflowRunRepository`.
- `src/aeat/application/workflow/_engine.py` contains `WorkflowEngine`.
  Workflow is an orchestration gate and must not own source calculation logic.

Model-by-model source inventory from committed registry data:

- Modelo `036` declares `profile`.
- Modelo `100` declares `ledger_renta_expense_aggregation`, `manual_input`,
  `previous_filing`, and `profile`.
- Modelo `130` declares `previous_filing`.
- Modelo `131` declares `manual_input` and `previous_filing`.
- Modelo `180` declares `previous_filing`.
- Modelo `184` declares `atribucion_member`.
- Modelo `190` declares `previous_filing` and `withholding`.
- Modelo `193` declares `previous_filing` and `withholding`.
- Modelo `200` declares `previous_filing`.
- Modelo `202` declares `previous_filing`.
- Modelo `232` declares `manual_input` and `related_party_operation`.
- Modelo `303` declares `ledger_iva_aggregation` and `previous_filing`.
- Modelo `309` declares `ledger_iva_aggregation`.
- Modelo `322` declares `ledger_iva_aggregation`.
- Modelo `349` declares `collectible_invoice`.
- Modelo `353` declares `ledger_iva_aggregation`.
- Modelo `360` declares `refund_operation`.
- Modelo `369` declares `ledger_oss_aggregation`.
- Modelo `390` declares `ledger_iva_aggregation` and `previous_filing`.
- Modelo `720` declares `foreign_asset` and `manual_input`.

Connectivity facts that constrain the implementation:

- IVA ledger calculation is connected today through transaction
  `taxable_base`, `iva_rate`, and `iva_amount`, plus canonical IVA rate
  validation. It is not connected through issued or received invoice line
  evidence by default.
- Renta ledger expense calculation is connected today through outgoing or
  refund transactions, business proportionality, spending category profiles,
  and received purchase invoice evidence. It is annual and first-slice only.
- Retenciones aggregation exists for 111, 115, 123, 180, 190, and 193, but it
  is not currently enrolled as an automatic bucket repository resolver for
  modelo calculation.
- Issued and received invoice catalogues exist and can be cross-linked with
  ledger transactions. They are not the default IVA source for 303 or 390.
- Payable and collectible invoice stores exist separately from the rich domain
  invoice catalogue. They must be treated as separate source adapters until
  unified by a canonical evidence abstraction.
- Region and CCAA exist in profile and Modelo 100 registry bindings. Expense
  category profiles are year-keyed, not region-keyed. If deductibility rules
  vary by region, current category profile and Renta context shapes are
  insufficient.
- Filing approval staleness currently does not fingerprint every source that
  can affect a future mesh-backed calculation. Invoice, fincas, inventory,
  profile, wallet, and live-source fingerprints must be resolver-provided.

## Implementation

Introduce a canonical calculation source mesh under `aeat.application.aggregation`.

Define `CalculationSourceContext` as the typed input to source resolution. It
contains bucket id, modelo, filing year, period, selected registry revision,
active profile facts needed for source selection, repository handles or
repository factories, and the calculation timestamp.

Define `ModeloSourceResolver` as the application port implemented by each
source adapter. A resolver declares the registry binding source kinds it owns
and exposes a resolution method for one `CalculationSourceContext`.

Define `CalculationSourceResolution` as the only payload that can feed
source-derived facts into modelo calculation. It carries decimal binding
values, enum binding values, bound casilla inputs, row values where the export
pipeline needs repeat rows, source object refs, source transaction ids,
diagnostic issues, and provenance.

Define `CalculationSourceMesh` as the orchestrator. It inspects the selected
`ModeloRevision`, runs every resolver whose declared sources are present,
refuses unhandled source-backed bindings unless the binding is explicitly
manual, rejects duplicate binding or bound-casilla writes without declared
precedence, and returns one merged resolution.

Move the current ledger IVA and Renta bridge into resolvers or wrap it through
the new mesh. `calculate_modelo_revision_from_bucket_aggregation` can remain as
a compatibility facade during the transition, but the default calculation
entrypoint should be mesh-backed.

Change `app modelo work calculate` to call the mesh-backed calculation path.
Manual `--binding` and `--casilla` values should be merged only after resolver
ownership checks. Caller-provided values must not override source-owned
bindings or source-owned bound casillas.

Enroll source families incrementally:
ledger IVA aggregation; ledger Renta expense aggregation; prior filing and
relation sources; Modelo 100 borrador prefill; IVA compensation wallet;
invoice and counterpart observations; withholding; foreign assets; profile
enum bindings; fincas/property income and amortization; inventory and
stock/amortization once inventory persistence is canonical.

Add a connectivity gate. For every committed modelo revision, every binding
source kind must be one of: handled by an enrolled resolver, explicitly manual,
or explicitly not yet operator-calculable with a surfaced diagnostic. Silent
zero from a missing resolver is not allowed.

Implement the migration in mechanical phases:

Phase 1: define contracts. Add strict models for `CalculationSourceContext`,
`CalculationSourceResolution`, source refs, source fingerprints, and resolver
diagnostics. Add a protocol for `ModeloSourceResolver`. The protocol must
declare owned binding sources and return typed values, typed issues, and typed
provenance.

Phase 2: wrap existing behavior. Register resolvers for
`ledger_iva_aggregation`, `ledger_renta_expense_aggregation`,
`ledger_oss_aggregation`, `profile`, `previous_filing`, borrador bindings, IVA
wallet decisions, and relation values without changing their domain semantics.

Phase 3: generalize ownership checks. Replace `_ledger_binding_ids` with a
resolver-owned binding and casilla ownership map. Reject manual collision
against every source-owned binding, not only ledger-owned bindings.

Phase 4: make CLI calculation mesh-backed. Route `app modelo work calculate`
through the mesh-backed bucket calculation path. Preserve manual values only
after ownership checks.

Phase 5: enroll invoice and evidence families. Adapt `InvoiceCatalogue`,
`PurchaseInvoiceEvidenceService`, `PayableInvoiceService`, and
`CollectibleInvoiceService` into canonical source observations for
counterpart, invoice-row, withholding, issued-invoice income, and received
purchase evidence use cases.

Phase 6: enroll retenciones. Connect `RetencionObservation` production to
real repositories so withholding models and Renta relations can trace
withholding source data by period, scheme, perceptor, invoice, and transaction.

Phase 7: harden Renta region context. If category deductibility is
region-specific, key category profiles by filing year plus CCAA or regime, and
carry the selected region in `RentaDeductibilityContext`.

Phase 8: enroll fincas and inventory only after persistence hardening. Add
source resolvers for property income, property expenses, imputation,
amortization, inventory movement, and valuation only after secure storage,
bucket identity, and source fingerprints are canonical.

Phase 9: expand staleness and audit. Require every resolver to contribute
source fingerprints to filing approval basis and calculation revision
provenance.

Add a real CLI regression. Seed an active bucket with classified transactions
through the real ledger/application repository path, create a Modelo 303 work
unit, run the CLI calculate command, and assert ledger-derived binding
overrides, bound casilla values, typed observations, source transaction ids,
and bucket event provenance.

## Rationale

This decision treats financial-to-modelo wiring as a first-class application
boundary, not as a special case inside one modelo or CLI command. The engine
should receive a complete source resolution envelope; it should not know how
to read ledgers, invoices, inventory, profiles, or live AEAT captures.

The mesh matches the existing project architecture. Source-specific facts are
projected by application services; registry formulas and binding resolvers
remain pure; CLI commands drive application ports; secure repositories remain
outbound adapters.

The mesh also makes missing work visible. When a modelo declares a binding
source and no resolver is enrolled, the operator should see a diagnostic that
names the missing source family. They should not receive a plausible all-zero
draft that looks ready for filing.

## Consequences

The immediate fix is small in concept but high impact: the CLI calculate path
must call the bridge that already exists for bucket-local ledger aggregation.

The longer-term implementation will add a new application-layer abstraction
and migrate current bridge code into resolvers. This introduces some
orchestration complexity, but it concentrates complexity in one place instead
of scattering source-specific glue across CLI, modelo actions, and registry
helpers.

Some current source domains will be blocked from modelo enrollment until their
storage and provenance are hardened. Inventory is the clearest example because
the current application service writes JSON under the ledgers directory while
the broader financial pipeline uses secure object repositories.

The registry may need additional validation that distinguishes manual binding
sources from source-backed binding sources. That validation should remain
registry-local and should not import application resolvers.

The project gains a durable extension pattern: future source domains are
usable for tax filing only when they implement a resolver, typed diagnostics,
provenance, source refs, and real-behavior connectivity tests.
