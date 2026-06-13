---
step_id: S166
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S166 — review-status enum membership tests

## Outcome

Added 3 real-behavior tests to `src/aeat/application/invoices/test_projection.py`
asserting that `invoice_review_status` returns `InvoiceReviewStatus` enum members
at each of the three former bare-string sites (PENDING, REVIEWED, PAID). Tests call
the production function directly with real `Invoice` and `InvoiceReviewRecord` objects.
No mocks, no skips, no tautologies.

## Tests added

| Test | Asserts |
| --- | --- |
| `test_invoice_review_status_pending_is_enum_member` | `isinstance(result, InvoiceReviewStatus)` + `result is PENDING` |
| `test_invoice_review_status_reviewed_is_enum_member` | `isinstance(result, InvoiceReviewStatus)` + `result is REVIEWED` |
| `test_invoice_review_status_paid_is_enum_member` | `isinstance(result, InvoiceReviewStatus)` + `result is PAID` |

## Files touched

| File | Change |
| --- | --- |
| `src/aeat/application/invoices/test_projection.py` | 3 new isinstance tests + import of `InvoiceReviewStatus` and `invoice_review_status` |

## Test result

5/5 new tests pass. 427 total pass across the targeted suite.

## Commit

`632f29dc0` — `review-status(S165-S166): replace bare review-status strings with StrEnum members`
