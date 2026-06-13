---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S26'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P07.S26 preserve modelo root command compatibility after extraction

Scope: `W03.P07` modelo CLI compatibility and validation.

## Description

- Preserve `modelo work calculate` source-shape compatibility for the existing bucket source-mesh boundary test.
- Repair the `modelo work` UX fixture so each cached CLI invoke opens the active UUID bucket session through the root callback.
- Resolve scoped Ruff findings in `_modelo`, including the missing `_emit_envelope` import for the M036 helper.

## Outcome

The focused command compatibility checks and the full modelo-work UX module pass after the extraction.

## Notes

Whole-file `_modelo.py` type checks still expose the known monolithic baseline. The new extracted modules pass `ty`; full `_modelo.py` Pyright and `ty` findings remain tracked as residual W03 complexity debt.
