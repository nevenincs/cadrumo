---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S58'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update modelo work UX tests for central redaction of identifiers

## Scope

- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Validate `src/aeat/entrypoints/cli/test_modelo_work_ux.py` against the centralized JSON output path.
- Remove temporary `DBG146` stderr probes from `src/aeat/application/modelo/_actions.py`; the probes polluted Click mixed output and made JSON-mode CLI results unparsable.
- Repair the stale workflow helper call in `src/aeat/application/workflow/_models.py` by routing active transaction catalogue resolution through `require_active_bucket_id()`.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_modelo_work_ux.py --tb=short -vv` passed: 11 passed.
- `uv run pytest -q src/aeat/application/workflow/test_transaction_catalogue_resolution.py --tb=short -vv` passed: 2 passed.
- `uv run pytest -q src/aeat/entrypoints/cli/test_output_surface_inventory.py --tb=short -vv` passed: 3 passed.
- `uv run ruff check src/aeat/application/modelo/_actions.py src/aeat/application/workflow/_models.py` passed.

## Notes

- The S58 redaction tests themselves were not weakened. The fixes removed production output contamination and repaired an adjacent active-bucket resolution regression so the real CLI behavior can be asserted.
