---
step_id: S38
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

# core-authority W04.P12.S38 — STRICT_FROZEN_CONFIG canonical declaration + first 5 migrations (MERGE-014)

## Files created

- `src/aeat/core/_models.py` — declares `STRICT_FROZEN_CONFIG: ConfigDict = ConfigDict(strict=True, frozen=True, extra="forbid")`

## Files modified

- `src/aeat/core/__init__.py` — exports `STRICT_FROZEN_CONFIG`

## Modules migrated (first 5)

All 5 migrated from `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")` (local) to `from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN` (canonical):

1. `src/aeat/domain/attachments/_models.py`
2. `src/aeat/domain/filing/_amendment.py`
3. `src/aeat/domain/fincas/_models.py`
4. `src/aeat/domain/invoices/_models.py`
5. `src/aeat/domain/invoices/_service.py`

## Verification

```
python -c "from aeat.domain.attachments._models import Attachment; from aeat.domain.filing._amendment import AmendmentKind; from aeat.domain.fincas._models import Finca; from aeat.domain.invoices._models import Invoice; from aeat.domain.invoices._service import ReconciliationSuggestion; print('OK')"
# → OK
```
