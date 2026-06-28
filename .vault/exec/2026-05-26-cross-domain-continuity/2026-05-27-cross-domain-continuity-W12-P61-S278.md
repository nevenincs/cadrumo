---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S278
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W12.P61.S278 — typed payload models (application + CLI layer)

## Outcome

Replaced four `dict[str, object]` payload functions in the application-ledger
layer with typed pydantic models, eliminating the primary UNTYPED_BOUNDARY
sites in the ledger workflow surface.

### Changes

**`src/aeat/application/ledger/_models.py`** — three new typed models:
- `LedgerTransactionReviewPayload` — typed projection of a transaction for
  review-list rows (all fields `str | None`, no domain types)
- `LedgerTransactionResultPayload` — typed result wrapper with
  `transaction: LedgerTransactionPayload`
- `LedgerTransactionTrackingPayload` — typed tracking projection, preserves
  `TransactionEvidenceProvenanceEntry`, `TransactionEditLineageEntry`, and
  `TransactionLifecycleLineageEntry` domain types as tuple fields
- `LedgerReviewRow.transaction` field type changed from `dict[str, object] | None`
  to `LedgerTransactionPayload | None`

**`src/aeat/application/ledger/__init__.py`** — new typed models added to
public API surface (`__all__` + `from ._models import ...`).

**`src/aeat/application/ledger/_actions.py`** — four function return types
and implementations updated:
- `ledger_transaction_payload` now returns `LedgerTransactionPayload` directly
  (dropped `.model_dump(mode="python")` at the function boundary)
- `ledger_transaction_review_payload` returns `LedgerTransactionReviewPayload`
- `ledger_transaction_result_payload` returns `LedgerTransactionResultPayload`
- `ledger_transaction_tracking_payload` returns `LedgerTransactionTrackingPayload`

**`src/aeat/entrypoints/cli/_ledger.py`** — seven call sites updated:
- `_emit_update_result`: attribute access (`transaction_payload.date`) +
  `.model_dump(mode="python")` at JSON boundary
- `ledger_add`: same pattern
- `ledger_link`: `evidence_result_payload.model_dump(mode="python")`
- `ledger_list`: `review_payload.model_dump(mode="python")` spread into row dict
- `ledger_view`: `result_payload.transaction` + `_field(value: object)` helper
  refactored from key-string to direct attribute pass
- `ledger_track`: `.model_dump(mode="python")` for both sub-payloads

### Commit isolation note

`_actions.py` and `_ledger.py` had peer WIP (Task #125 bulk-classify additions)
mixed in the working tree. Clean commit required reconstructing HEAD + my changes
only, then restoring peer WIP after the commit. Peer work preserved in working
tree untouched.

## Commits

- `c25b14a54` — W12.P61.S278: typed payload models + caller updates

## Files changed

- `src/aeat/application/ledger/_models.py` — three new typed models + LedgerReviewRow.transaction typed
- `src/aeat/application/ledger/__init__.py` — public API exports updated
- `src/aeat/application/ledger/_actions.py` — four payload functions typed
- `src/aeat/entrypoints/cli/_ledger.py` — seven caller sites updated
