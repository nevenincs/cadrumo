---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S39'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# B1 Extract a secure-object catalogue integrity-error wrapper and route the exact-shape repositories through it

## Scope

- `src/aeat/adapters/persistence/storage/errors.py`

## Description

- Confirmed the four modelo catalogue repositories (calculation-revision,
  filing-record, work-unit, verification-report) share the byte-identical
  integrity-except shape: positional `"<label> catalogue integrity error"`
  message + `translated_message` + `{reason: secure_object_integrity,
  cause_type}` context, chained `from exc`.
- Added `raise_catalogue_integrity_error(exc, *, error_cls, label,
  translated_message, logger)` to `domain/modelos/_errors.py` and routed the
  four repos through it, passing each repo's own logger so log source is
  preserved.

## Outcome

Committed as `0ea544c08`, tagged `relocation:raise_catalogue_integrity_error`
(5 files, +58/-36). Ruff clean; 108 modelos repo/roundtrip/integrity tests green.
Behaviour-identical.

## Notes

Excluded from this exact-shape helper: `buckets/_event_repository` (its context
keys are namespace/object_key, a different shape) and `domain/modelos/
_participation_index` (peer-WIP at edit time). The four exact-shape repositories
— the step's scope — are done.
