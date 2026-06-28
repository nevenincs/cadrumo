---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S35'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C2 Replace module-local _STRICT_FROZEN re-declarations with the aliased canonical import

## Scope

- `src/aeat/core/_models.py`

## Description

- Found ten module-local `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True,
  extra="forbid")` re-declarations (single- and multi-line, with/without
  `: Final`), all peer-clean and exactly canonical-shape.
- Scripted (dry-run-reviewed) the removal of each declaration + insertion of
  `from <depth>core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN`; `ruff --fix`
  dropped the now-unused `ConfigDict`/`Final` imports and sorted.

## Outcome

Committed as `b84d73f8b`, tagged `relocation:STRICT_FROZEN_CONFIG` (10 files,
+23/-45). Ruff clean; collect-only clean (897 collected); 459
auth/iva_compensation/calculations/reconciliation tests green.

## Notes

Excluded `_cross_period_clean_state` (peer-WIP at edit time) and
`core/json_contract._STRICT_FROZEN_CONFIG` (carries `validate_assignment=True`
— constraint-divergent, keeps its own config per the core/_models carve-out).
