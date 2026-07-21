---
tags:
  - '#exec'
  - '#session-honest-followups'
date: '2026-07-05'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-06-02-session-honest-followups-plan]]"
---

# Clarify EncryptedString str-vs-bytes round-trip on object_key column

## Scope

- `src/aeat/adapters/persistence/storage/sql/_orm.py`

## Description

- Backfill the missing execution record for checked Step `P03.S18`.
- Recover diagnostic evidence from commit `660f8486c1`.
- Record the historical finding that the encrypted column raw read returns opaque bytes by design and consumers should use accessors.

## Outcome

- `P03.S18` has a canonical exec record linked to the parent plan.
- The old closeout resolved the concern as behavior-by-design rather than landing an ORM change.
- No source files were changed by this backfill.

## Notes

- This is a diagnostic closure record, not a fresh storage round-trip proof.
