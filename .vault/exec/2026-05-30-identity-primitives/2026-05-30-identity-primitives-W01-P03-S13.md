---
step_id: S13
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W01.P03.S13 — delete BucketId from domain/modelos/_ids

## Scope

Remove the `BucketId` alias declaration and its `__all__` entry from
`src/aeat/domain/modelos/_ids.py` per identity-primitives ADR Rule 5,
update the module docstring to reflect the remaining four-alias
contract, and repoint the two intra-package private re-aliases in
`domain.modelos._work_unit` and `domain.modelos._filing_record` so they
import `BucketId as _BucketId` from `aeat.core.identity` rather than
from the now-empty `._ids` slot. The full collapse of the private
re-alias blocks is deferred to W03.P11 per the plan.

## Outcome

- `domain/modelos/_ids.py` no longer declares `BucketId`. The `__all__`
  tuple lists four aliases: `CalculationRevisionId`, `FilingRecordId`,
  `TransactionId`, `WorkUnitId`.
- The module docstring is rewritten to remove the prior justification
  that "BucketId and TransactionId are declared here because the
  modelo boundary records reference both" and to record the
  ADR-driven move of the bucket identity to `core.identity`.
- `domain/modelos/_work_unit.py` and `domain/modelos/_filing_record.py`
  resolve `_BucketId` via `from ...core.identity import BucketId as
  _BucketId`.

## Verification

- `rg "^BucketId\s*=" src/aeat/` reports one occurrence at
  `src/aeat/core/identity/_bucket.py`.
- `rg "modelos\._ids import.*BucketId|from \._ids import .*BucketId|from \.\._ids import .*BucketId" src/aeat/`
  reports zero matches.
- `python -c "import aeat.domain.modelos._work_unit,
  aeat.domain.modelos._filing_record,
  aeat.domain.modelos._calculation_revision; from
  aeat.core.identity import BucketId; print('ok')"` resolves cleanly.

## Commit

`536617600` — refactor(modelos): remove BucketId declaration from domain/modelos/_ids
