---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S01'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W01.P01.S01 Execution

Inventory completed for `work revisions` and `work revision` in `src/aeat/entrypoints/cli/_modelo.py`.

Findings:
- Both commands were CLI transport and presentation surfaces around application selectors and revision persistence.
- The command dependencies were `list_calculation_revisions`, `get_work_unit`, `modelo_202_modality_for_work_unit`, revision payload rendering, selector error conversion, and active-profile resolution.
- The extraction boundary is a focused CLI registrar that receives resolver callables and emits existing payload/envelope shapes.
