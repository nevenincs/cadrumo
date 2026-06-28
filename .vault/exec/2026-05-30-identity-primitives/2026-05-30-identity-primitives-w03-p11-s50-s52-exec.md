---
step_id: S50
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W03.P11.S50-S52 — delete private re-alias blocks

## Scope

Delete the private `as _<Name>` re-alias import blocks at
`domain/modelos/_work_unit.py`, `domain/modelos/_filing_record.py`,
and `domain/modelos/_calculation_revision.py` per ADR Rule 4
(cross-package consumers import the alias by its public name,
never re-alias under a private name) and rewrite consuming fields
to reference the aliases under their public names.

## Outcome

`src/aeat/domain/modelos/_work_unit.py`:
- `from ...core.identity import BucketId as _BucketId` and
  `from ._ids import WorkUnitId as _WorkUnitId` collapsed to plain
  imports.
- `WorkUnit.work_unit_id` and `WorkUnit.bucket_id` consume
  `WorkUnitId` and `BucketId` directly.

`src/aeat/domain/modelos/_filing_record.py`:
- All four private re-alias imports collapsed.
- `ModeloRecord` fields `filing_record_id`, `work_unit_id`,
  `calculation_revision_id`, `bucket_id`,
  `superseded_by_filing_record_id`, `amends_filing_record_id`
  consume the aliases under their public names.

`src/aeat/domain/modelos/_calculation_revision.py`:
- Both private re-alias imports collapsed.
- `CalculationRevision.calculation_revision_id`, `work_unit_id`,
  `source_transaction_ids`, `amends_filing_record_id` consume the
  aliases under their public names.

## Verification

- `uv run --no-sync pytest src/aeat/domain/modelos/` returns
  `147 passed` after each Step.

## Plan steps closed

`W03.P11.S50`, `S51`, `S52`.
