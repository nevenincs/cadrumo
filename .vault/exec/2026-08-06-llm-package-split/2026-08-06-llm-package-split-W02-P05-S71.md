---
tags:
  - '#exec'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:5e03f38c9f103628a2b3731c28f3681f8103b2f7341fd7c6955a6776d1ad3006'
step_id: 'S71'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
---

# Assert the keyed guard compares every persisted field so a same-key re-add whose content differs refuses with an instructive conflict, red if a re-add changing one field is reported as an unchanged no-op and the new value is silently dropped

## Scope

- `src/cadrumo/application/ledger/tests/`

## Description

- Compare EVERY persisted field in the keyed guard, not a subset.
- Refuse a same-key re-add whose content differs, naming each changed field.
- Add a coverage assertion that the comparison set is complete against the caller-supplied field list.

## Outcome

A same-key re-add that changes one field is refused with an instructive conflict naming that field, rather than reported as an unchanged no-op.

The second assertion is what makes the first durable. A guard that matches on a subset silently drops whatever changed in the fields it did not inspect -- an under-declaration wearing an idempotency guard's clothes. The coverage test fails when a new caller-supplied field is added without being enrolled in the comparison, so the guard cannot rot as the record grows.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_idempotency.py -m "unit or integration" -n 0
    5 passed in 0.29s

## Notes

RECONSTRUCTED RECORD, as for S69.

Worth noting for whoever reads this next: the same defect class was found independently on the manual ledger path during the invoice campaign's close review -- a guarded no-op whose match omitted a persisted field, so a retry changing only that field silently dropped the new value. Two campaigns hit the same shape on different records, which is the argument for the coverage assertion rather than a hand-maintained field list.
