---
tags:
  - '#adr'
  - '#t6-aggregation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-t6-aggregation-research]]"
  - "[[2026-04-17-export-first-adr]]"
---

# `t6-aggregation` adr: `classified-catalogue-to-casilla-ledger` | (**status:** `accepted`)

## Problem Statement

Kent has classified transactions and category profiles, but no T6 component turns them into the `Mapping[str, Decimal]` consumed by the Modelo calculation engine. The gap forces him back to a spreadsheet at the exact point where the workflow should compute his quarterly Modelo 130 liability.

## Considerations

The existing formula engine is already strict and Decimal-only. The transaction catalogue is a frozen aggregate loaded from encrypted FINANCIAL persistence. Category profiles are strict, but their current Modelo 130 expense mapping is not compatible with the ruleset's `01` income / `02` expense semantics. The workflow already has an inputs-provider protocol, so T6 should implement that boundary rather than invent a second workflow contract.

## Constraints

Live AEAT submission stays out of scope. All new boundary models are pydantic v2 frozen models. Imports inside `src/aeat` remain relative. User-facing errors must inherit from `AeatError` and be registered. CLI output must support the shared JSON schema registry. Tests must use real catalogue/profile instances and module-level `unit` plus `domain_financial_input` markers.

## Implementation

Create `src/aeat/domain/financial/aggregation/` as the T6 package. It owns `Period`, `CasillaAggregation`, `CasillaProvenance`, typed errors, the aggregation service, and a concrete `FinancialFilingInputsProvider`.

`Period` is a strict frozen model with `raw`, `year`, optional `quarter`, optional `month`, `start`, `end`, and `period_type`. It accepts `YYYY-Qn`, `YYYYQn`, `YYYY-MM`, and `YYYY`; ambiguous or unsupported input raises `AggregationPeriodError`.

`CasillaAggregation` carries `modelo`, `period`, `casilla_values`, and `provenance`. `CasillaProvenance` carries `casilla`, `transaction_ids`, `subtotal`, and `category_id`. Mapping fields are frozen through validators and serialized as normal JSON objects.

The aggregation algorithm walks the loaded catalogue in memory, filters by inclusive `Period` boundaries, requires classified business-relevant rows, skips personal rows, requires category coverage for outgoing expense rows, applies `business_pct` for `MIXED`, applies directly numeric profile proportionality (`fixed_pct` or `default_ratio`), treats `NON_DEDUCTIBLE` as zero, and otherwise treats `FULL_DEDUCTIBLE` / uncapped supported rows as one. For Modelo 130, incoming business rows feed `01`; outgoing mapped expense rows feed `02` unless an explicit mapping points to a different compatible input casilla. Transaction amounts are aggregated by absolute value so bank debit sign conventions do not leak into tax casilla values.

`FinancialFilingInputsProvider.load_inputs(modelo, period, profile)` loads the configured transaction catalogue through `TransactionCatalogueRepository`, aggregates, and returns `casilla_values` as `Mapping[str, Decimal]`. The existing workflow protocol's `profile` parameter remains accepted but is not part of the aggregation decision in this issue.

M303 is deferred for calculation correctness. The shared backend can carry M303 later, but current transactions lack VAT bases/rates and current category mappings point to a result casilla. The provider therefore only returns Modelo 130 inputs unless an explicitly supported mapping path is added later.

## Rationale

This design reuses the current encrypted catalogue repository and workflow inputs seam, keeping persistence and workflow architecture stable. The separate aggregation package gives T6 a typed public surface without overloading `transactions` or `categories`. Deferring M303 avoids shipping a ledger that looks authoritative while aggregating the wrong VAT concepts.

## Consequences

The first implementation is in-memory over the catalogue aggregate. If a later SQL repository exposes queryable transactions, the provider can swap its loading strategy without changing `CasillaAggregation`. Statutory caps need a follow-up model extension because per-day and per-person facts do not exist on current transactions. The category registry's M130 expense mapping should be corrected or bypassed defensively in the aggregator tests so Kent's `02` expense value is correct.
