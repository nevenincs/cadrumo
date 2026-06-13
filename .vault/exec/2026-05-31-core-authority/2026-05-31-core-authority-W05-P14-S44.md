---
step_id: S44
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

# core-authority W05.P14.S44 — EvidenceTier collapse to _schema.py (RENAME-004)

## Files modified

- `src/aeat/domain/calculations/registry/_workbook_parity.py` — removed 6-line `EvidenceTier` declaration; added `EvidenceTier` to the existing `from ._schema import` line

## Commit

`92d1039f7` — refactor(registry): collapse EvidenceTier to single definition in _schema.py (RENAME-004 W05.P14.S44)

## Before / After

Both declarations were identical 4-member Literals:
```python
EvidenceTier = Literal[
    "legal_authority",
    "official_source_guidance",
    "executable_parity_evidence",
    "layout_authority",
]
```

`_schema.py` is canonical (already imported by `_coverage.py`). `_workbook_parity.py` now imports from `_schema`. `_parity_tapes.py` imports `EvidenceTier` transitively from `_workbook_parity` (re-exported via module attribute), confirmed to still work.

## Genuine collapse (not false-positive)

Both files had identical 4 members. The `_workbook_parity.py` copy was a pure duplication with no domain rationale for divergence.

## Test run

```
python -c "from aeat.domain.calculations.registry._workbook_parity import EvidenceTier; print(EvidenceTier)"
# → typing.Literal['legal_authority', 'official_source_guidance', 'executable_parity_evidence', 'layout_authority']
```
