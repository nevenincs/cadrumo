---
step_id: "S25"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S25

**Status**: closed

## What was done

Introduced `BindingPrefillTypeError(CoreValidationError)` in `src/aeat/application/calculations/_errors.py`, appended after the existing `IvaCompensationModeloError`.

Replaced both bare `TypeError` raises in `src/aeat/application/calculations/_binding_prefill.py` (in `_selector_year_delta` at line 56 and `_selector_periods` at line 65) with `raise BindingPrefillTypeError(...)`.

Registered the new error under code `REFUSED_BINDING_PREFILL_TYPE` (category `REFUSED`, message key `errors.refused.refused_calculations_casilla_constraint`) in `src/aeat/core/errors/registry/_application.py`, appended after the `IvaCompensationModeloError` entry.

## Files touched

- `src/aeat/application/calculations/_errors.py` — added `BindingPrefillTypeError(CoreValidationError)`
- `src/aeat/application/calculations/_binding_prefill.py` — imported `BindingPrefillTypeError`; replaced two `TypeError` raises
- `src/aeat/core/errors/registry/_application.py` — registry entry for `BindingPrefillTypeError`

## Commit

`62529675a`
