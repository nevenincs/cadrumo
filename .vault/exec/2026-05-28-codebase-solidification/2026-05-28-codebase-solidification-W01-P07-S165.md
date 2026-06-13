---
step_id: S165
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S165 — review-status bare-string migration

## Outcome

Migrated 4 raw review-status string return sites to typed StrEnum members.
`ReviewState` in `_enums.py:67` and `LedgerReviewStatus` in `_filter.py:143`
are **distinct** — `ReviewState` (PENDING/ALL) is a UI filter toggle; `LedgerReviewStatus`
(PENDING/REVIEWED/SKIPPED) is the operator transaction status catalogue. No convergence
required; they serve separate semantics.

`invoice_review_status` in `_projection.py` was updated to return `InvoiceReviewStatus`
(PENDING/REVIEWED/PAID) since the invoice domain supports a `"paid"` state absent from
`LedgerReviewStatus`. `ledger_transaction_review_status` in `_actions.py` was updated
to return `LedgerReviewStatus`. The `status_counts` dict was also typed as
`dict[LedgerReviewStatus, int]` with enum-keyed construction and lookup.

## Files touched

| File | Sites migrated | Change |
| --- | --- | --- |
| `src/aeat/application/invoices/_projection.py` | 3 | return type + 3 return sites → `InvoiceReviewStatus` |
| `src/aeat/application/ledger/_actions.py` | 3 | return type + 3 return sites → `LedgerReviewStatus`; dict typed |

## Enum distinction

`_enums.py:67` `ReviewState` — two members (PENDING/ALL): controls which review-queue
items the CLI emits. Not a status taxonomy.

`_filter.py:143` `LedgerReviewStatus` — three members (PENDING/REVIEWED/SKIPPED):
the canonical status for operator transaction classification decisions. These are the
values returned by `ledger_transaction_review_status`.

## Collision check

`git diff` on all target files returned no output before edits. Clean workspace confirmed.

## Test result

427 tests pass across `src/aeat/application/invoices/`, `src/aeat/application/ledger/`,
and `src/aeat/application/review/`. 5 pre-existing failures in `test_actions.py` export
tests (`source_jurisdiction` unknown field) are unrelated to this step.

## Commit

`632f29dc0` — `review-status(S165-S166): replace bare review-status strings with StrEnum members`
