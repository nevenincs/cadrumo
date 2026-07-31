---
tags:
  - '#exec'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:17c93e352388a55b6df4af0baebbda5927201140ad19db847d61cd3c7c4cf7e9'
step_id: 'S05'
related:
  - "[[2026-07-02-arch-remediation-data-budget-plan]]"
---

# Declare the corpus-split escape hatch as a named constant beside the budget carrying its target condition so the option is discoverable in code

## Scope

- `src/aeat/tests/test_data_size_budget.py`

## Description

- Declare the corpus-split escape hatch as a named constant `_CORPUS_SPLIT_ESCAPE_HATCH` beside the budget, carrying its target condition, and surface it in the breach message.

## Outcome

The ADR Option B escape hatch is discoverable in code, not only in prose.

## Notes
