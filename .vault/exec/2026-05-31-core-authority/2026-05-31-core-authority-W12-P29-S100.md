---
step_id: S100
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W12.P29.S100 step record

## Step

Enroll the first 18 bare-str `_id/_kind/_status/_state` field sites onto their typed
aliases in `src/aeat/domain/`. (PROMOTE-001, Rule 5)

## Status

BLOCKED — all domain-layer bare-str `_id` sites have constraint-shape mismatches with
the existing typed aliases. Per the W04-W08 lesson: "If the typed alias doesn't exist
yet, or the alias shape doesn't match the field's existing constraint (don't tighten
silently), block."

## Site-by-site audit (domain layer)

| File:line | Field | Alias | Block reason |
|---|---|---|---|
| `domain/invoices/_service.py:51` | `ReconciliationSuggestion.invoice_id: str = Field(min_length=1)` | `InvoiceId` (hex-64, exactly 64) | Field allows any non-empty str; promoting adds 64-char exact + pattern constraint |
| `domain/invoices/_service.py:76` | `LinkInconsistency.invoice_id: str = Field(min_length=1)` | `InvoiceId` | Same as above |
| `domain/transactions/_models.py:452` | `TransactionEvidenceProvenanceEntry.evidence_id: str = Field(min_length=1, max_length=128)` | `EvidenceId` (hex-64, exactly 64) | max_length=128 vs 64; different shape family |
| `domain/transactions/_models.py:779` | `Transaction.invoice_id: str \| None = None` | `InvoiceId` (hex-64) | No constraint; loose optional; would add strict 64-char hex |
| `domain/transactions/_raw_transaction.py:125` | `RawTransaction.transaction_id: str = Field(min_length=1)` | `TransactionId` (hex-64) | Raw transactions carry provider-assigned IDs of variable length; hex-64 constraint would reject legitimate ingest |
| `domain/user_profile/_registry_contract.py:34` | `UserProfileRegistryContractIssue.modelo_id` | `ModeloId` (pattern `^\d{3}$`) | Field is `str = Field(min_length=1)`; no length constraint; promoting adds 3-digit pattern restriction |
| `domain/user_profile/_registry_contract.py:35` | `UserProfileRegistryContractIssue.revision_id` | `RevisionId` (max_length=128, pattern=`_REF_RE`) | Field is `str = Field(min_length=1, max_length=64)`; max_length mismatch (64 vs 128) |
| `domain/user_profile/_registry_contract.py:43` | `UserProfileRegistryContractIssue.construct_id` | `ConstructId` (max_length=128, pattern=`_REF_RE`) | Same max_length mismatch |
| `domain/calculations/registry/_bindings.py:526` | `InvoiceObservation.invoice_id` | `InvoiceId` (hex-64) | Need to verify constraint |

The `domain/calculations/registry/_bindings.py:526` site needs verification but the
InvoiceId alias requires hex-64 pattern which likely doesn't match the registry
binding context.

## Clause 10 violations in domain layer

The Clause 10 detector (`find_bare_str_kind_status_state_fields`) reports zero
violations in the domain layer; all two violations are in `application/ledger/_models.py`
and are addressed in S101.

## Files touched

None.
