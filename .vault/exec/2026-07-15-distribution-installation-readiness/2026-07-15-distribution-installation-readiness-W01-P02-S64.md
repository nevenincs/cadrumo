---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S64'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Run the full grounded MCP oracle in the scrubbed installed-environment regression

## Scope

- `src/cadrumo/entrypoints/mcp/tests/test_installed_cli_resolution.py`

## Description

- Replace the shallow installed `contract` probe with the complete public MCP tax-work oracle.
- Build and install the committed root wheel plus both mandatory data companions into one fresh environment.
- Launch the absolute installed MCP executable outside the checkout with product commands removed from `PATH`.
- Assert the grounded result, exact legal reference, revision-bound observation URI, and direct calculation tool call.

## Outcome

- The installed scrubbed-path regression completed the full Modelo 200 itinerary and persisted grounded observations.
- The test proved `DP200014:00562=23000.00`, formula `modelo-200-cuota-integra`, and direct dispatch through `cadrumo_modelo_work_calculate`.
- Ruff and ty passed; the real artifact build, install, `pip check`, MCP launch, sibling CLI execution, calculation, and resource read passed in 357.19 seconds.

## Notes

- The test uses only committed source through the archive build helper; unrelated checkout changes cannot enter the installed wheel.
