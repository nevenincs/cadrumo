---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` `W04.P70` summary

- Modified: `src/aeat/application/workflow/_engine.py`
- Created: `src/aeat/entrypoints/cli/tests/test_modelo_200_stored_calculation_drift_cli.py`
- Created: `2026-05-26-cross-domain-continuity-W04-P70-S421.md`

## Description

S421 closes the stored-calculation-drift traceback discovered by the fresh Modelo 200 S.A. persona. Known `ModeloBuilderError` failures at the workflow draft-builder seam now become a persisted `DRAFT_HAS_ERRORS` step with the exact missing-relation evidence and a recalculate action. The separate broad exception path remains responsible for unexpected failures.

The real encrypted-storage CLI regression creates and calculates a legal-entity Modelo 200 work unit, records an activity-start date after calculation, and verifies it. The result remains a typed `REFUSED_MODELO_WORKFLOW_GATE` refusal naming the missing relation; no traceback leaks in CLI output or workflow logs. Independent review approved the narrower catch order and the real-behaviour test.
