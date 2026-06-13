---
step_id: S103
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
  - "[[2026-05-31-core-authority-audit]]"
---

# core-authority W13.P30.S103 step record

## Step

Verify CTIMEX-003 is resolved: `application/filing/__init__.py` imported `utc_now`
from the deleted `aeat.core._time` module. Confirm the import now points at
`core.time._clock._now` and that `pytest --collect-only` on `application/filing/`
reports zero ImportErrors.

## Root cause

Commit `309d5fc10` (parallel campaign `chore/eliminate-shims`, W07.P33 S528-S530)
deleted `src/aeat/core/_time.py`, but `application/filing/__init__.py` line 10 still
read `from ...core._time import utc_now as _utc_now`. This caused a `ModuleNotFoundError`
on import, breaking collection across the filing test suite.

## Resolution

The WIP working tree already carried the fix (applied during the W12 close-gate
investigation). The corrected import on line 10 is:

```python
from ...core.time._clock import _now as _utc_now
```

`core/time/_clock.py` exports `_now` which is the canonical `utc_now` equivalent.
All other callers (`application/auth/_actions.py`, `application/workflow/_utils.py`, etc.)
were already migrated to `core.time._clock._now` in earlier steps.

## Verification

```
uv run --no-sync python -m pytest src/aeat/application/filing/ --collect-only -q
234 tests collected in 0.15s
```

Zero ImportErrors. All 234 filing tests collect cleanly.

## Files touched

- `src/aeat/application/filing/__init__.py` — line 10 redirected from `core._time` to `core.time._clock`
