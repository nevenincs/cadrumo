---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S43'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P12.S43 - centralized revision-pick resolution

Scope: implement centralized revision-pick resolution from modelo work targets, selectors, explicit revision ids, and command-specific defaults.

## Description

- Add `ModeloCalculationRevisionDefault` to the application selector surface.
- Add `resolve_modelo_calculation_revision_pick` in `src/aeat/application/modelo/_selectors.py`.
- Move command-specific default selection for verify, file, and export into the selector policy surface.
- Rewire `resolve_modelo_calculation_revision_address` to delegate revision-pick policy to `_selectors.py`.
- Add `resolve_modelo_revision_pick` to project a selected revision back to owning work-unit id, short ids, selector, and state metadata.
- Export the new selector and projection helpers from the public `aeat.application.modelo` package facade.

## Outcome

Calculation revision selection now has one application policy path for current, latest-draft, latest-verified, filed, explicit id, and verify/file/export defaults. CLI and adjacent consumers can import the public facade instead of reimplementing local selector branching.

## Notes

Verification commands passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_selectors.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_work_addressing.py src/aeat/application/modelo/test_selectors.py`
- `uv run --no-sync python -m compileall -q src/aeat/application/modelo/_selectors.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/test_work_addressing.py`
- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py src/aeat/application/modelo/test_work_addressing.py -q`
- `rg -n "resolve_modelo_calculation_revision_pick|resolve_modelo_revision_pick|ModeloRevisionPick|ModeloCalculationRevisionDefault" src/aeat/application/modelo`
- `uv run --no-sync vaultspec-rag search "resolve_modelo_revision_pick ModeloRevisionPick ModeloVisibleFilingTarget ModeloExactWorkUnitTarget" --type code --language python --max-results 12 --port 8766 --json`
