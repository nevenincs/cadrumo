---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S10'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Harden import deduplication provenance and gap diagnostics

## Scope

- `src/aeat/application/ledger`

## Description

- Harden import duplicate fingerprints with currency and parsed direction.
- Preserve legacy and stamped fingerprint matching for existing catalogue rows.
- Restore verified re-import duplicate diagnostics after the direction-qualified
  persistence change.

## Outcome

Commit `34873aa5a` added direction and currency discriminators to persisted
import fingerprints. Re-review found duplicate diagnostics had lost the
direction signal; commit `2c78a89d` fixed
`src/aeat/application/transactions/_import.py` and
`src/aeat/application/ledger/_actions_import.py` so diagnostics receive the same
direction-qualified fingerprints as persistence.

## Notes

Final focused ledger verification passed 62 tests with 7 deselected, including
`test_actions_review_query_imports.py` and transaction import diagnostics tests.
