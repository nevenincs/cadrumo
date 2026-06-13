---
tags:
  - '#research'
  - '#ledger-renta-pipeline'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-04-14-transaction-catalogue-review-audit]]"
  - "[[2026-04-17-invoice-catalogue-research]]"
  - "[[2026-04-13-p2e-tax-category-catalogue-research]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-research]]"
  - "[[2026-04-28-modelo-100-renta-full-calc-reference]]"
  - "[[2026-05-08-aeat-cli-hardening-inventory-audit]]"
---



# `ledger-renta-pipeline` research: `live-ledger-to-renta-calculation-state`

Research into the live ledger backend, invoice association model,
category/proportionality substrate, calculation registry surfaces,
Modelo 100/Renta modeller boundaries, and existing tests that already
bind ledger-shaped data into registry calculations.

The purpose is to identify what is already implemented and where the
next decisions sit before ledger state can become legally grounded
Renta calculation input.

## Findings

### Live Ledger Backend State

- `src/aeat/domain/transactions/_models.py` defines the persisted
  ledger domain: `RawTransaction`, `Transaction`,
  `TransactionCatalogue`, `ClassificationHistoryEntry`, and
  `derive_transaction_id`.
- `Transaction` is the current canonical classified ledger record. It
  carries `transaction_id`, `raw`, `direction`,
  `business_classification`, `business_pct`, `invoice_id`,
  `category_id`, classification metadata, and
  `classification_history`.
- `BusinessClassification.MIXED` is the only classification that allows
  `business_pct`; non-mixed classifications reject a business
  percentage at model validation time. This gives the ledger a live
  personal/business split concept, but it is not yet an evaluated Renta
  deductible-share model.
- `derive_transaction_id` hashes provider identity, value date, amount,
  and narrative, so repeated imports can be made idempotent without
  depending on mutable review state.
- `src/aeat/domain/transactions/_repository.py` implements
  `TransactionCatalogueRepository`, which is the live persistence
  boundary for transaction catalogues. It stores an encrypted secure
  object under namespace `aeat.domain.transactions` and object key
  `catalogue`; `load` returns an empty `TransactionCatalogue` when no
  object exists.
- `TransactionCatalogueRepository.merge_raw_transactions` imports raw
  bank rows into the catalogue using `derive_transaction_id` and leaves
  existing classified records intact.
- `src/aeat/domain/transactions/_service.py` provides live mutation
  operations: `find_transaction`, `link_invoice`, `set_classification`,
  and `snapshot_classification_state`.
- `set_classification` appends `ClassificationHistoryEntry` only when
  the classification signature changes. It accepts `category_id`,
  `business_pct`, `classified_by`, `reason`, and `confidence`, but it
  does not resolve category proportionality or produce calculation
  binding values.
- `link_invoice` writes `Transaction.invoice_id` on the ledger side.
  The bidirectional invoice/ledger association is implemented in the
  invoice service rather than inside the transaction repository.
- `src/aeat/entrypoints/cli/_ledger.py` exposes user-facing ledger
  operations through `ledger_import`, `ledger_review`, and
  `ledger_edit`.
- `src/aeat/application/user_cli.py` contains the review UI state model:
  `LedgerSplit`, `LedgerReviewRecord`, `UserCliStateRepository`, and
  `update_ledger_review`. `LedgerSplit` stores
  `business_share`/`personal_share` and enforces that they sum to one.
  That review state is separate from `Transaction.business_pct`; there
  is no live adapter that automatically reconciles review splits into
  persisted transaction classification or Renta inputs.
- `src/aeat/entrypoints/cli/_common.py` currently leaves
  `_aggregate_filing_inputs` as a placeholder returning `{}`. This is
  the most important live gap for the user-facing declaration flow:
  `declaration_calculate` cannot yet pull persisted ledger, invoice,
  category, profile, or rental data into filing calculations.

### Invoice Association Model

- `src/aeat/domain/invoices/_models.py` defines `InvoiceLine`,
  `Invoice`, `InvoiceCatalogue`, and `derive_invoice_id`.
- `InvoiceLine` carries `description`, `quantity`, `unit_price`,
  `subtotal`, `iva_rate`, `iva_amount`, and `category_id`. The line
  category is available as factual classification input, but it is not
  currently evaluated into Renta expense treatment.
- `Invoice` carries `kind`, invoice identity, counterparty fields,
  totals, `lines`, `payment_status`, `linked_transaction_ids`,
  `iva_category`, `retention_rate`, `retention_amount`, and
  `payment_id`.
- `Invoice.iva_classification_for_line` delegates to
  `classify_invoice_line_for_iva`, so IVA classification is already
  modeled from invoice facts.
- `src/aeat/domain/invoices/_repository.py` implements
  `InvoiceCatalogueRepository`, storing an encrypted secure object under
  namespace `aeat.domain.invoices` and object key `catalogue`.
- `src/aeat/domain/invoices/_service.py` provides `find_invoice`,
  `find_unmatched`, `link_transaction`, `suggest_reconciliations`,
  `verify_link_consistency`, and `link_transaction_bidirectional`.
- `link_transaction_bidirectional` is the live consistency operation
  for invoice/ledger association. It loads both
  `InvoiceCatalogueRepository` and `TransactionCatalogueRepository`,
  updates `Invoice.linked_transaction_ids` and
  `Transaction.invoice_id`, then saves both catalogues.
- `suggest_reconciliations` uses amount and counterparty heuristics
  against real invoice and transaction catalogues. It suggests matches;
  it does not create calculation observations.
- `src/aeat/domain/invoices/_iva_classification.py` is the current
  bridge from invoice lines to calculation substrate. It defines
  `IvaInvoiceClassification`, `classify_invoice_line_for_iva`,
  `invoice_line_to_iva_observation`, and produces
  `IvaLedgerObservation` for standard domestic issued/received IVA.
- `invoice_line_to_iva_observation` deliberately rejects
  `IvaRate.NOT_SUBJECT`, reverse-charge, intracommunity, and OSS/IOSS
  cases unless explicitly modeled elsewhere. This keeps the existing
  bridge narrow and legally safer for Modelo 303 style aggregation.

### Category And Proportionality State

- `src/aeat/domain/categories/_spending_category.py` defines the closed
  category vocabulary: `SpendingCategory`, `SpendingCategoryFamily`,
  `family_for`, and `categories_for_family`.
- `src/aeat/domain/categories/_profile.py` defines `CategoryProfile`
  and the local VAT hint enum `VatCategory`. `CategoryProfile` carries
  `category`, `display_label`, `proportionality`, and optional
  `vat_hint`.
- `src/aeat/domain/categories/_proportionality.py` defines the legal
  proportionality model: `CategoryCitationSource`,
  `CategoryCitation`, `ProportionalityKind`,
  `StatutoryCapPeriod`, `StatutoryCapVariant`, and
  `ProportionalityRule`.
- `ProportionalityKind` currently supports `FULL_DEDUCTIBLE`,
  `FIXED_PERCENTAGE`, `USAGE_RATIO_PERSONAL`,
  `USAGE_RATIO_HOME_AREA`, `STATUTORY_CAP`, `NON_DEDUCTIBLE`, and
  `REQUIRES_EXCLUSIVE_USE`.
- `ProportionalityRule` requires citations and validates
  kind-specific fields such as `fixed_pct`, `default_ratio`, and
  statutory caps. This is the strongest existing legal-grounding
  substrate for expense categories.
- `src/aeat/domain/categories/_registry.py` provides
  `load_category_profile_file`, `load_category_profile_registry`, and
  `resolve_category_profiles`.
- `src/aeat/domain/categories/test_registry.py` verifies that every
  category has a profile, every profile has citations, proportionality
  kinds carry the required fields, and representative categories have
  expected semantics.
- `src/aeat/domain/categories/test_profile.py` verifies that category
  profiles carry category semantics and explicitly reject stale casilla
  projection payloads.
- The live gap is evaluator-shaped: there is no observed implementation
  that takes `Transaction.category_id`, `Transaction.business_pct`,
  `InvoiceLine.category_id`, `CategoryProfile.proportionality`, and
  `ProportionalityRule` citations and emits Renta binding values or
  casilla inputs.
- Category identifiers on `Transaction` and `InvoiceLine` are stored as
  optional strings at the model boundary. CLI/service paths can choose
  `SpendingCategory`, but persisted data still needs validation or
  normalization before it becomes a legal calculation source.

### Registry And Calculation Surfaces

- `src/aeat/domain/calculations/registry/_schema.py` defines
  `DataBindingDefinition`. Its `source` field already admits
  `ledger`, `invoice`, `rental`, `vat`, `category`, `profile`,
  `previous_filing`, `manual_input`, `ledger_oss_aggregation`, and
  `ledger_iva_aggregation`.
- `DataBindingDefinition` carries `selector`, `aggregation`,
  `typed_enum`, `legal_refs`, and `source_refs`. That is the right
  place for legal provenance of registry-owned binding definitions.
- `CasillaDefinition.input_kind` supports `manual`, `bound`,
  `computed`, and `informational`. Bound casillas can already receive
  values resolved from binding definitions.
- `FormulaExpression` can reference `casilla`, `binding`,
  `parameter`, `relation`, and `literal` leaves.
- `src/aeat/domain/calculations/registry/_formula_runtime.py` provides
  `calculate_registry_snapshot`. It evaluates formulas using explicit
  `inputs`, `binding_values`, and `relation_values`; it does not
  resolve persisted ledger or invoice repositories by itself.
- `read_parameter` is the public non-formula parameter reader already
  used by rental/Renta logic. This is an existing precedent for domain
  code consuming registry-owned legal parameters without duplicating
  rates in the domain module.
- `src/aeat/domain/calculations/registry/_bindings.py` implements the
  live binding resolvers for invoice observations, OSS/IOSS ledger
  aggregation, IVA ledger aggregation, previous filings, and relation
  observations.
- `InvoiceObservation`, `IvaLedgerObservation`, and
  `OssIossLedgerObservation` are side-effect-free observation models.
  They are not repository adapters. Callers must convert persisted
  catalogues into these observations before invoking resolver functions.
- `resolve_ledger_iva_aggregation_binding_values` and
  `resolve_ledger_oss_aggregation_binding_values` already provide a
  mature pattern for legally typed ledger aggregation: validate binding
  definitions, filter observations by typed dimensions, aggregate base
  or tax amounts, and return binding values for registry calculation.
- `src/aeat/domain/calculations/registry/__init__.py` exports the
  registry binding substrate as public API, including
  `IvaLedgerObservation`, `OssIossLedgerObservation`,
  `InvoiceObservation`, resolver functions, `RegistryQueryService`, and
  `calculate_registry_snapshot`.

### Modelo 100 And Renta Modeller Surfaces

- `src/aeat/domain/renta/_substrate.py` defines closed Renta enums:
  `RentaIncomeType`, `RentaCCAA`, and
  `EstimacionDirectaModalidad`.
- `EstimacionDirectaModalidad` maps the normal/simplificada choice to
  binding `renta-2025-modelo-100-estimacion-directa-es-normal` with raw
  values `N` and `S`. Renta consumers should use the enum rather than
  hard-coded strings.
- The registry TOML state shows Modelo 100 currently has no
  ledger/category/rental binding source. For years 2020 through 2024,
  Modelo 100 has only one `manual_input` binding and all substantive
  casilla values are manual or informational. For 2025, Modelo 100 has
  `manual_input`, `profile`, and `previous_filing` bindings, with 30
  bound profile casillas, 35 computed casillas, 9 relations, 164
  formulas, 10 application links, and 2 live references.
- The observed Modelo 100 2025 profile bindings are a live modeller
  surface, but they are not yet ledger expense or income bindings.
- `src/aeat/domain/rental/_aggregates.py` implements
  `compute_rental_aggregates`, which aggregates rental contracts,
  income, expenses, amortization, and imputation facts from live rental
  repositories into `RentalAggregates`.
- `src/aeat/domain/rental/_tier_resolver.py` consumes registry
  parameters through `read_parameter`, grounding rental thresholds and
  rates in the registry rather than in duplicated Python constants.
- `compute_rental_aggregates` intentionally avoids filing-line
  identifiers; the filing targets remain registry-owned. That is a
  useful model for future ledger-to-Renta design.
- Rental carry-forward remains incomplete:
  `_existing_carry_forward` returns an empty tuple and logs that
  prior-year excess is not consumed.
- `src/aeat/application/filing/__init__.py` implements `build_draft`.
  It loads a `RegistrySnapshot`, extracts casilla and binding inputs
  from `FilingInputs`, and calls `calculate_registry_snapshot`. It does
  not resolve source data from ledger, invoice, rental, category, or
  profile repositories.
- `src/aeat/entrypoints/cli/_declaration.py` calls
  `_aggregate_filing_inputs` before building a draft, so the current
  CLI declaration path has a deliberate aggregation seam but no live
  implementation behind it.
- `src/aeat/application/filing/_review.py` fingerprints transaction
  catalogues and category profiles through
  `compute_current_approval_basis`, `approval_stale_reasons`,
  `_transaction_catalogue_fingerprint`, and
  `_category_profiles_fingerprint`. This already ties ledger/category
  state to filing approval freshness, but not to calculation values.

### Existing Tests Binding Ledger Data Into Calculations

- `src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py`
  uses the real registry tree and verifies Modelo 303 ledger IVA
  binding behavior through `IvaLedgerObservation` and
  `resolve_ledger_iva_aggregation_binding_values`.
- Those tests cover canonical binding validation, base amount
  aggregation, IVA amount aggregation, category/rate/direction filters,
  zero results for no matches, and multi-binding resolution.
- `src/aeat/domain/calculations/registry/test_ledger_oss_aggregation_binding.py`
  uses real Modelo 369 registry data and verifies
  `OssIossLedgerObservation` aggregation through
  `resolve_ledger_oss_aggregation_binding_values`.
- OSS/IOSS tests cover regime, destination state, VAT rate,
  direction, transaction kind, base amount, and IVA amount filters.
- `src/aeat/domain/invoices/test_iva_classification.py` verifies
  `invoice_line_to_iva_observation` and includes
  `test_invoice_line_observation_feeds_modelo_303_binding_resolver_end_to_end`,
  which converts invoice-line facts into `IvaLedgerObservation` and
  feeds the real Modelo 303 binding resolver.
- `src/aeat/domain/calculations/registry/test_invoice_bindings.py`
  exercises `InvoiceObservation`, `resolve_invoice_binding_values`,
  `resolve_invoice_binding_row_values`, and
  `invoice_binding_requirements` against real registry definitions.
  This is invoice-source binding coverage, but it uses observation
  inputs rather than persisted `InvoiceCatalogueRepository` state.
- `src/aeat/domain/calculations/registry/test_modelo_369_registry.py`
  demonstrates the full registry pattern:
  `resolve_ledger_oss_aggregation_binding_values`,
  `resolve_bound_casilla_inputs`, then
  `calculate_registry_snapshot`.
- `src/aeat/domain/calculations/registry/test_modelo_303_registry.py`,
  `src/aeat/domain/calculations/registry/test_modelo_309_registry.py`,
  `src/aeat/domain/calculations/registry/test_modelo_322_registry.py`,
  `src/aeat/domain/calculations/registry/test_modelo_353_registry.py`,
  and
  `src/aeat/domain/calculations/registry/test_modelo_390_registry.py`
  contain additional real-registry coverage around IVA binding and
  calculation behavior.
- `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`
  exercises Renta formula behavior with real registry data, manual
  inputs, and explicit binding/relation values. It does not consume
  ledger data.
- `src/aeat/domain/calculations/registry/test_renta_2025_synthetic_profile.py`,
  `src/aeat/domain/calculations/registry/test_registry_scenarios.py`,
  and
  `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
  cover Renta/profile/formula scenarios with caller-supplied values.
  They do not establish a persisted ledger-to-Renta path.
- `tests/integration/calculations/test_rental_threshold_registry_grounded.py`
  confirms rental threshold and rate lookup is registry-grounded for
  supported Renta years. It is important legal-grounding precedent, but
  it is not ledger binding coverage.
- `src/aeat/domain/calculations/registry/test_schema_hygiene.py`
  enforces that Renta typed binding candidates declare the substrate
  enum class.
- `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
  asserts that the ledger binding substrate is part of the public
  registry API.

### Main Gaps

- There is no live repository adapter from
  `TransactionCatalogueRepository` or `InvoiceCatalogueRepository` to
  Renta binding values.
- There is no Renta-specific observation model equivalent to
  `IvaLedgerObservation` or `OssIossLedgerObservation`.
- There are no Modelo 100 registry bindings with source `ledger`,
  `category`, or `rental` in the observed registry state. The schema
  allows those sources, but the Renta registry revisions do not use
  them yet.
- `_aggregate_filing_inputs` is empty, so the CLI declaration path does
  not connect persisted user state to `FilingInputs`.
- Category proportionality is legally modeled and tested, but not
  evaluated against ledger amounts.
- Invoice-to-IVA observation conversion exists, but there is no
  persisted catalogue scan that applies period filters, reconciled
  transaction links, category profiles, retentions, and proportionality
  rules for Renta.
- `build_draft` is calculation-only. It accepts already resolved
  `FilingInputs` and binding values; it is not responsible for fetching
  or legally classifying user data.
- Approval staleness already fingerprints ledger/category state, but
  calculated Renta values do not yet include provenance that points back
  to the ledger transactions, invoices, categories, and legal citations
  used to derive them.

### Next Decision Points

- Decide whether Renta ledger bindings should use the existing generic
  source values `ledger`, `category`, and `rental`, or whether a
  narrower source such as `renta_ledger_aggregation` should be added to
  mirror `ledger_iva_aggregation` and `ledger_oss_aggregation`.
- Define the observation contract for Renta ledger facts. A likely
  contract needs transaction identity, date, amount, direction,
  business share, category, invoice link, income/expense role,
  proportionality result, and provenance fields that can cite both the
  category rule and the registry binding definition.
- Decide where proportionality is evaluated. The current registry
  pattern suggests factual/legal classification should happen before
  `calculate_registry_snapshot`, with the registry owning binding IDs,
  casilla targets, formulas, source references, and legal references.
  The category registry would remain the source for category-specific
  proportionality citations.
- Define how `Transaction.business_classification`,
  `Transaction.business_pct`, `LedgerSplit.business_share`,
  `InvoiceLine.category_id`, and `CategoryProfile.proportionality`
  reconcile when they disagree.
- Decide whether Renta should privilege invoice lines, ledger
  transactions, or linked invoice/transaction pairs for deductible
  expenses. The legal and audit model should make duplicate counting
  impossible.
- Define period and fiscal-year filters for ledger and invoice facts
  before they become Renta observations.
- Decide how retentions and payments should enter Modelo 100: through
  invoice facts, ledger movements, explicit previous-filing bindings, or
  separate payment-domain observations.
- Add registry-level Modelo 100 bindings only after the legal mapping is
  explicit. Binding definitions should carry `legal_refs` and
  `source_refs`, while category profiles should carry category-specific
  `CategoryCitation` evidence.
- Extend real-behavior tests without fakes or skipped shortcuts. The
  first useful tests should create real catalogues, classify/link real
  transactions and invoices, resolve Renta binding values, and run
  `calculate_registry_snapshot` against real Modelo 100 registry data
  with non-tautological expected results.
