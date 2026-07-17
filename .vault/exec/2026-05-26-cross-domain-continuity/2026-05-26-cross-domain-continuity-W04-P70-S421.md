---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S421'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Contain stored calculation drift after profile changes at the CLI error boundary and prove Modelo 200 verification returns only a typed actionable refusal

## Scope

- `src/aeat/application/modelo/ src/aeat/entrypoints/cli/ src/aeat/**/tests/`

## Description

- Trace `modelo work verify` from persisted calculation replay through the workflow draft-builder seam.
- Convert the typed `ModeloBuilderError` raised during draft construction into a failed `BUILDING_DRAFT` workflow step with `DRAFT_HAS_ERRORS`.
- Preserve the original error text and a recalculate instruction in the persisted step summary and details.
- Add a real encrypted-storage CLI regression that creates an S.A. profile, calculates Modelo 200, records an activity-start date through `config profile edit`, and verifies the stored calculation.
- Assert the CLI refusal carries the exact missing relation, `REFUSED_MODELO_WORKFLOW_GATE`, and `DRAFT_HAS_ERRORS`, without a traceback in either CLI output or workflow logs.

## Outcome

The post-profile-edit replay no longer crosses the unhandled-exception path. The missing `modelo-200-2024-rel-202-pagos-fraccionados` evidence remains visible in the typed refusal, while the workflow records `DRAFT_HAS_ERRORS` and emits no Python traceback. The regression uses the real CLI and isolated encrypted storage only; it introduces no mock, stub, fake, or patch seam.

## Notes

The repository's default pytest marker selection deselects integration tests, so the verified command explicitly selects the integration marker: `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_modelo_200_stored_calculation_drift_cli.py -q` (1 passed in 19.61s). `uv run --no-sync ruff check src/aeat/application/workflow/_engine.py src/aeat/entrypoints/cli/tests/test_modelo_200_stored_calculation_drift_cli.py` also passed.
