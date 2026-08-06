---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:b942f3dc86e398de47e33eff98b0d934e8b3246212e1be909e886f5e8bd604f1'
step_id: 'S364'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Add a bridge-justification docstring to _utils.py matching the five other documented Family-2 bridges (applicability.py, taxpayer_model.py, _ids.py, _schemas.py, _playwright.py), explaining why normalise_key and utc_now are re-exported through this shared workflow-application surface rather than imported directly from aeat.domain.contribuyente and aeat.core.time at each call site

## Scope

- `src/aeat/application/workflow/_utils.py`

## Description

- Confirmed the only production consumers of `normalise_key` / `utc_now` from this module are intra-package (`_events.py`, `_models.py`) plus the package top-level facade re-export.
- Added a module docstring naming this a documented Family-2 bridge per `import-centralization` ADR ruling 4, matching the shape of the five other documented bridges (`applicability.py`, `taxpayer_model.py`, `_ids.py`, `_schemas.py`, `_playwright.py`), stating why the two symbols are re-exported here rather than imported directly at each call site.
- No structural change to the exports or the two re-exported symbols.

## Outcome

Committed alongside S368, S369, and S388 in one commit (`b6aafa707`) covering all of Phase `W03.P87`'s small facade fixes. `ruff check`/`ruff format` clean; `pytest --collect-only -q src/aeat` clean; `src/aeat/application/workflow/tests` (108 tests) green.

## Notes

None.
