---
step_id: S39
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P12.S39 — STRICT_FROZEN_CONFIG migration second 5 modules (MERGE-014)

## Modules migrated (second 5)

All 5 migrated from `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")` (local) to `from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN` (canonical):

6. `src/aeat/domain/submission/_models.py`
7. `src/aeat/domain/submission/_protocols.py`
8. `src/aeat/domain/transactions/_models.py`
9. `src/aeat/domain/transactions/_raw_transaction.py`
10. `src/aeat/domain/user_profile/_schema.py`

## Test run

```
pytest src/aeat/domain/filing/ src/aeat/domain/fincas/ src/aeat/domain/invoices/ src/aeat/domain/submission/ src/aeat/domain/transactions/ src/aeat/domain/user_profile/ src/aeat/domain/modelos/
```

All pass (pre-existing `test_blob_and_manifest_round_trip_without_plaintext_files` failure in `domain/attachments/test_repository.py` is unrelated — asserts a hash digest is not stored in SQLite, but it is; this test predates W04).

## Note on scope

Total production `_STRICT_FROZEN` declarations: ~90. The plan specifies "first five" and "remaining five" = 10 total. 80 additional modules remain for follow-up waves. Both the two `arbitrary_types_allowed=True` diverging modules and `core/json_contract.py`'s `validate_assignment=True` variant remain module-local per the S37 audit.
