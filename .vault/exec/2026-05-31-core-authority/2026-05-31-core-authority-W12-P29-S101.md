---
step_id: S101
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W12.P29.S101 step record

## Step

Enroll the next 18 bare-str `_id/_kind/_status/_state` field sites onto typed aliases
across the application layer. Includes the W11-flagged `review_status: str` cluster.
(PROMOTE-001, Rule 5)

## Status

COMPLETE (2 sites promoted; remaining 16 sites blocked)

## Implementation

Promoted the two Clause 10 violations in `application/ledger/_models.py`:

- `LedgerTransactionReviewPayload.review_status: str = Field(min_length=1)` → `LedgerReviewStatus`
- `LedgerTransactionResultPayload.review_status: str = Field(min_length=1)` → `LedgerReviewStatus`

Added import of `LedgerReviewStatus` from `..review` at the top of `_models.py`.

`LedgerReviewStatus` is a `StrEnum` with members PENDING / REVIEWED / SKIPPED. The
pydantic model uses `strict=True`; StrEnum instances are `str` subclasses and are
accepted without coercion.

## Blocked application-layer sites (audit)

All remaining application-layer bare-str `_id` sites have constraint-shape mismatches
with their target typed aliases:

| File | Field | Alias | Block reason |
|---|---|---|---|
| `state_projection.py:85` | `ProjectionActiveProfile.profile_id: str \| None` | `ProfileId` (UUID4) | No constraint; bare optional; adding UUID4 pattern would reject non-UUID values |
| `state_projection.py:530,542` | `revision_id: str = Field(max_length=64)` | `RevisionId` (max=128, pattern) | max_length mismatch + pattern addition |
| `aggregation/_iva_ledger.py:89,99` | `transaction_id: str = Field(max_length=128)` | `TransactionId` (hex-64 exact) | max_length 128 vs 64 |
| `aggregation/_renta_income_ledger.py:68,97` | `transaction_id: str` | `TransactionId` | Same |
| `aggregation/_renta_ledger.py:81` | `transaction_id: str` | `TransactionId` | Same |
| `aggregation/_source_mesh.py:67,68` | `binding_id/casilla_id: str = Field(max_length=256)` | aliases (max=128/64) | max_length mismatch |
| `invoices/_linking.py:26,27` | `invoice_id/transaction_id: str` | hex-64 aliases | No constraint; promoting adds 64-char exact |
| `invoices/_queries.py:30` | `InvoiceListRow.invoice_id: str` | `InvoiceId` (hex-64) | No constraint |
| `invoices/_reconciliation.py:26,27` | `invoice_id/transaction_id: str` | hex-64 aliases | No constraint |
| `ledger/_business_operation_invoice.py:161` | `invoice_id: str` | `InvoiceId` | No constraint |
| `ledger/_evidence.py:61` | `evidence_id: str = Field(max_length=64)` | `EvidenceId` | Test context uses `uuid4().hex[:16]` (16 chars) |
| `ledger/_models.py:553,688,699,727` | `transaction_id: str` | `TransactionId` | No constraint or max=128 |
| `ledger/_preflight.py:50` | `transaction_id: str = Field(max_length=128)` | `TransactionId` | max_length mismatch |
| `review/_models.py:146,156` | `transaction_id/invoice_id: str = Field(min_length=1)` | hex-64 aliases | min_length=1 allows any str |
| `live/_borrador_100.py:64` | `snapshot_id: str = Field(max_length=128)` | `SnapshotId` (hex-64) | Different family per _snapshot.py docstring |
| `live/_censo.py:107,109` | `snapshot_id/profile_id: str` | SnapshotId/ProfileId | Different constraint families |
| `user_profile/_censo_sync.py:89,112` | `snapshot_id: str = Field(min_length=1)` | `SnapshotId` | Different family |
| `user_profile/__init__.py:231,250,260,264,277` | `revision_id/snapshot_id: str` | varying | max_length mismatch or different family |
| `storage/calc_sheets/_parity_harness.py:105` | `modelo_id: str` | `ModeloId` | No constraint |
| `storage/calc_sheets/_records.py:439` | `modelo_id: str` | `ModeloId` | No constraint |

## Clause 10 result

`find_bare_str_kind_status_state_fields()` reports 0 violations (was 2 before this step).

## Commit

`e5d630f5d` — promote(ledger): W12.P29.S101 - review_status bare-str fields to LedgerReviewStatus

## Files touched

- `src/aeat/application/ledger/_models.py`
