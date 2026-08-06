---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:ca2d1fa7eaa3f4399cd8c6edfadd2457f640530c1cb7925092b2b8e640764341'
step_id: 'S10'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Carry created_at and updated_at onto the canonical aggregate or record their loss as a deliberate decision in the execution record, so no slim field disappears unremarked

## Scope

- `src/cadrumo/domain/invoices/_models.py`

## Description

- Measured whether the record-lifecycle fact is conserved anywhere else on the canonical side before deciding to carry or drop it.
- Added both stamps to the canonical aggregate as OPTIONAL fields, outside the derived identity.
- Added a coercion hop for the strict model, mirroring the one the date fields already use, refusing an unreadable stamp rather than defaulting it.
- Added a strict save-load equality roundtrip with both stamps populated non-default and distinct from the document date, plus the anti-tautology half.
- Extended the test module docstring so its stated coverage stays true, rather than leaving prose that no longer describes the file.
- Raised the wider gap this measurement exposed as its own Step.

## Outcome

**Decision: carry, not drop.** The Step allowed either, provided the choice was deliberate. The measurement decided it.

The record-lifecycle fact is when the RECORD was entered and last amended, which is a different fact from when the document was issued and from when the operation occurred. Nothing on the canonical side carried it, and nothing else conserved it either, so dropping it would have been an unremarked loss of an audit fact rather than a redundancy.

Three properties of the implementation are load-bearing:

- **Optional, not required.** A canonical invoice that genuinely carries no recorded entry time must be able to say so. The alternative is stamping the current time at construction, which manufactures an audit fact nobody observed. `None` means "not recorded", never "recorded as now" — the conservation law bars a synthesised value standing in for one the source never held.
- **Outside the derived identity.** Folding a clock into the invoice id would mint a new record on every retry, which the idempotency rule bars. These are last-seen body fields.
- **Refuses rather than defaults on an unreadable value.** The strict model would not re-parse a serialised stamp on load without a coercion hop, and that hop refuses malformed input. Defaulting to `None` would convert "this record's history is corrupt" into "this record has no history", which reads as normal and would never be investigated.

**The measurement exposed a second, wider gap that no Step in this plan named, now raised as `S37`.** The slim services emit six dedicated bucket event types on create, update and remove, and return their ids in the operator's mutation result. **The canonical invoice write paths emit no bucket event of any kind** — not on creation, not on mutation, not on deletion. Confirmed against the creation, lifecycle, linking and bulk-import modules together.

That makes two consequences the deletion phase would otherwise absorb silently. Repointing the bare verbs onto the canonical aggregate drops the invoice audit trail and the event-ids field from the operator's mutation result in the same change. And deleting the slim store removes the only emitter of six enum members, which is a retired-enum reconciliation rather than a deletion.

The timestamps and the events are the same capability seen from two sides — what changed, and when — so closing only the field half would leave the audit story half-conserved.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py -p no:randomly -q --no-header
    7 passed in 7.38s

Regression scope for a change to the shared aggregate:

    uv run --no-sync pytest src/cadrumo/domain/invoices src/cadrumo/application/invoices -q --no-header
    331 passed in 20.34s

    uv run --no-sync ruff check src/cadrumo/domain/invoices/_models.py src/cadrumo/domain/invoices/tests/test_secure_storage_roundtrip.py
    All checks passed!

The intermediate RED is quoted because it is what forced the coercion hop rather than a silent widening of the field type:

    ValidationError: 1 validation error for Envelope[InvoiceCatalogue]
    payload.invoices.<id>.updated_at
      Input should be a valid datetime [type=datetime_type, input_value='2025-06-11T16:45:30Z', input_type=str]

The absence claim behind `S37` was measured, not assumed:

    rg -n "BucketEventType|append_event|record_event|bucket_event" application/invoices/{_creation,_lifecycle,_linking,_bulk_import}.py
    (no matches)

## Notes

The two stamps are added but **not yet populated by any writer**. The aggregate can now hold the fact and the boundary provably preserves it, which is what this Step owed the fold. Populating them on the canonical write paths belongs with `S37`, since a write that stamps the record and emits no event, or emits an event and leaves the record unstamped, is the same audit story told half-way.

The field addition touches the canonical `Invoice` model, which a peer campaign's ADR constrains. Read in full that constraint is narrower than it is usually quoted — it bars altering the model in ways that couple it to profile state, and these are plain optional scalars with no such coupling — but the reconciliation with that lane is still outstanding and is tracked against the same open item as the bucket-attribution Step.
