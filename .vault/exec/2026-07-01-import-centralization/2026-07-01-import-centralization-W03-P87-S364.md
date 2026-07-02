---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S364'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S364 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add a bridge-justification docstring to _utils.py matching the five other documented Family-2 bridges (applicability.py, taxpayer_model.py, _ids.py, _schemas.py, _playwright.py), explaining why normalise_key and utc_now are re-exported through this shared workflow-application surface rather than imported directly from aeat.domain.contribuyente and aeat.core.time at each call site and ## Scope

- `src/aeat/application/workflow/_utils.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
