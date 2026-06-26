---
tags:
  - '#reference'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
  - '[[2026-06-26-bindings-architecture-unification-audit]]'
---



# `binding-source-kind-taxonomy-unification` reference: `source-kind taxonomy current-state anchor inventory`

The concrete current-state code anchors the phase-2.1 ADR
(`2026-06-26-binding-source-kind-taxonomy-unification-adr`) decides over and the
plan's steps will edit. Every site is the source-kind closed set declared, typed,
or used as a bare string. Anchors verified at HEAD `cbf749f5a` on branch
`chore/eliminate-shims`; re-confirm each immediately before editing (fast-landing
shared worktree). Line numbers drift — treat the symbol name as authoritative and
the line as a hint.

## Summary

### 1. The source-kind declarations (the four-plus parallel taxonomies)

All in `src/aeat/core/aggregation.py` unless noted:

- `BindingSourceKind` (StrEnum, ~line 182) — the declared-canonical registry set,
  **19 members**: `PROFILE`, `PREVIOUS_FILING`, `RELATION_PREFILL`, `MANUAL_INPUT`,
  `LEDGER_OSS_AGGREGATION`, `LEDGER_IVA_AGGREGATION`, `LEDGER_RENTA_EXPENSE_AGGREGATION`,
  `LEDGER_RENTA_INCOME_AGGREGATION`, `LEDGER_RENTA_GASTO_AGGREGATION`,
  `RETENCIONES_AGGREGATION`, `PAYABLE_INVOICE`, `COLLECTIBLE_INVOICE`,
  `LEDGER_TRANSACTION`, `PURCHASE_INVOICE_EVIDENCE`, `WITHHOLDING`, `FOREIGN_ASSET`,
  `RELATED_PARTY_OPERATION`, `ATRIBUCION_MEMBER`, `REFUND_OPERATION`. The four
  invoice/counterpart members take their VALUE from `AggregationSourceKind`; the two
  `WITHHOLDING`/`FOREIGN_ASSET` members take their value from `RowSetGroupingKind`.
  Enforced as a type ONLY at `DataBindingDefinition.source`.
- `AggregationSourceKind` (StrEnum, ~line 85) — **DUPLICATE to retire**, 4 members:
  `LEDGER_TRANSACTION`, `PURCHASE_INVOICE_EVIDENCE`, `PAYABLE_INVOICE`,
  `COLLECTIBLE_INVOICE`. All four values already exist as `BindingSourceKind`
  members. Used by the per-modelo aggregation service and counterpart taxonomy.
- `CounterpartSourceKind` (Literal subset of `AggregationSourceKind`, ~line 105) +
  `COUNTERPART_SOURCE_KINDS` frozenset (~line 113) + `counterpart_source_kind()`
  narrower (~line 123) — **re-express as a derived subset of `BindingSourceKind`**.
- `operator_surface.SourceKind` (StrEnum, `application/operator_surface/_models.py:43`)
  — **DUPLICATE to retire**, byte-identical 4 members to `AggregationSourceKind`,
  docstring "from the CLI workflow redesign ADRs".
- `RowSetGroupingKind` (StrEnum, ~line 151) — **KEEP as distinct downstream axis**
  (row-assembly grouping, not a source token), 5 members: `WITHHOLDING`,
  `RELATED_PARTY`, `FOREIGN_ASSET`, `ATRIBUCION`, `REFUND`. Bridged by
  `ROW_SET_GROUPING_FOR_BINDING_SOURCE` (~line 253). ADR proposes binding it as a
  derived projection of `BindingSourceKind` (total + gated), not merging it.

### 2. The parallel bare-string mesh vocabulary (to re-type to `BindingSourceKind`)

- `ModeloSourceResolver.owned_sources: tuple[str, ...]` — the port property,
  `application/aggregation/_source_mesh.py:127` (Protocol ~line 222).
- `CalculationSourceDiagnostic.source_kind: str` (`_source_mesh.py:103`) and
  `CalculationSourceProvenance.source_kind: str` (`_source_mesh.py:116`) — both
  `Field(min_length=1, max_length=64)`.
- `DEFERRED_SOURCE_KINDS: frozenset[str]` (`_source_mesh.py:66`) — 5 members:
  `withholding`, `atribucion_member`, `related_party_operation`, `foreign_asset`,
  `refund_operation` (all already `BindingSourceKind` members; Sheets-pull-only /
  defer-with-advisory).
- `_BUCKET_AGGREGATION_OWNED_SOURCES: frozenset[str]`
  (`application/modelo/_calculation_actions.py:146`) — 14 members:
  `ledger_iva_aggregation`, `ledger_renta_expense_aggregation`,
  `ledger_renta_income_aggregation`, `ledger_renta_gasto_aggregation`,
  `ledger_oss_aggregation`, `retenciones_aggregation`, `collectible_invoice`,
  `payable_invoice`, `previous_filing`, `relation_prefill`, `profile`, `borrador`,
  `iva_wallet_decision`, `manual_input`. Plus the derived subsets
  `_BUCKET_AGGREGATION_LOCK_SOURCES` and `_CALLER_OVERRIDABLE_CARRY_SOURCES`
  (~line 166 onward, used at `:743`/`:764`) and the novel-source gate
  `assert_no_novel_source_kinds` (~line 913).

### 3. Production resolver `owned_sources` string-literal sites (one enum member each)

Each is a `ModeloSourceResolver` declaring its owned source as a bare-string tuple:

- `relation_prefill` — `application/calculations/_relation_prefill.py:655`
  (`RelationPrefillSourceResolver`).
- `previous_filing` — `application/calculations/_multi_year.py:495`
  (`PreviousFilingSourceResolver`).
- `iva_wallet_decision` — `application/calculations/_iva_wallet_reconciliation.py:65`
  (`IvaWalletDecisionSourceResolver`). **Mesh-only token, no `BindingSourceKind`
  member at HEAD.**
- `borrador` — `application/modelo/_borrador_binding.py:193`
  (`Modelo100BorradorSourceResolver`, resolver_id `modelo_100_borrador`).
  **Mesh-only token, no `BindingSourceKind` member at HEAD.**
- `profile` — `application/aggregation/_source_profile.py:24` (`ProfileSourceResolver`).
- `ledger_oss_aggregation` — `application/aggregation/_oss_ioss.py:328`
  (`OssIossLedgerSourceResolver`).
- `ledger_iva_aggregation` — `application/aggregation/_modelo_bindings.py:161`.
- `ledger_renta_expense_aggregation` — `_modelo_bindings.py:251`.
- `ledger_renta_income_aggregation` — `_modelo_bindings.py:338`.
- `ledger_renta_gasto_aggregation` — `_modelo_bindings.py:428`.
- `retenciones_aggregation` — `_modelo_bindings.py:560`
  (`RetencionesAggregationSourceResolver`; the #6/#28 point-fix source — already a
  `BindingSourceKind` member, absorbed unchanged).
- `("collectible_invoice", "payable_invoice")` — `application/invoices/_source_resolver.py:51`
  (`InvoiceCatalogueSourceResolver`, via `_OWNED_SOURCES`).

### 4. Union gap analysis (the "neither set contains the other" defect)

- **Mesh-only** (owned-string with NO `BindingSourceKind` member): `borrador`,
  `iva_wallet_decision`. → ADR adds them as members (`BORRADOR`,
  `IVA_WALLET_DECISION`).
- **Registry-only** (`BindingSourceKind` member in NEITHER the owned nor the
  deferred mesh set): `purchase_invoice_evidence`, `ledger_transaction`. → ADR
  forces an explicit enrolled/deferred/reserved disposition for each.
- **Note:** `manual_input` is in `_BUCKET_AGGREGATION_OWNED_SOURCES` and is a
  `BindingSourceKind` member but is handled via the manual allowlist, not a resolver.

### 5. The parity gate to extend, and the homonyms to leave alone

- Extend `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`
  (today: enum↔registry parity) with an enum↔mesh half — every owned/deferred/
  resolver-owned source is a `BindingSourceKind` member, and every member is
  enrolled, pre-mesh-handled, deferred, or explicitly reserved-undeclared.
- **Genuine homonyms — NOT taxonomy members, leave untouched** (phase-4 naming
  concern): `ModeloReconciliationSourceKind` (`application/modelo/_reconcile.py:35`),
  `BusinessOperationInvoiceSourceKind` (`application/ledger/_business_operation_invoice.py:53`),
  `IvaCompensationAuthoritySourceKind` (`domain/iva_compensation/_reconciliation.py:48`).
