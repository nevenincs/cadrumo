---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S16'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The Consolidate the live-CLI _metric_line and auth-preflight guard onto shared helpers in _app_live_auth_preflight and redirect rendering, expedientes, justificante, notifications and ## Scope

- `src/aeat/entrypoints/cli/_app_live_auth_preflight.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Consolidate the live-CLI _metric_line and auth-preflight guard onto shared helpers in _app_live_auth_preflight and redirect rendering, expedientes, justificante, notifications

## Scope

- `src/aeat/entrypoints/cli/_app_live_auth_preflight.py`

## Description

- Keep the canonical `_metric_line` in `_app_live_auth_preflight.py`; add a shared
  `run_auth_preflight(preflight, *, family)` guard there.
- Redirect `_app_live_rendering.py` and `_app_live_expedientes_cli.py` to import
  `_metric_line`; remove their duplicate defs.
- Replace the per-module `_run_auth_preflight` guards in expedientes, justificante
  and notifications with calls to the shared `run_auth_preflight(..., family=...)`.

## Outcome

Five duplicate defs removed. 25 live-read-subgroup tests pass; ruff and
collect-only clean. Landed as commit `e59a4fb12`.

## Notes

Two failing tests in the wider run (`test_backend_boundary` skip-language meta-lint
and a `modelo reconcile` tax_id mismatch) are peer/pre-existing, outside this
surface.
