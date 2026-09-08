---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:37efb01a69879ca24f75096548c80eeb9c7c6a8064f95aff7f555b8150a899a0'
step_id: 'S207'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Amend the accepted filing-lifecycle decision to forbid production mapped-versus-excluded event inventories before a live producer owns the conversion, then delete the test-only lifecycle event mapping, exclusion enum/inventory, exports, and inventory-conformance tests while retaining the sanitized lifecycle wire vocabulary and projection behavior.

## Scope

- `Tuimodelo filing-lifecycle ADR`
- `declarations workspace and focused tests`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/adr/2026-09-07-tuimodelo-filing-lifecycle-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/modelo/declarations_workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_declarations_workspace.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/declarations_workspace.py src/cadrumo/application/modelo/tests/test_declarations_workspace.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> src/cadrumo/application/modelo/tests/test_declarations_workspace.py` -> `pass` (19 passed)
- `verify:` `rg -n "DECLARATION_LIFECYCLE_EVENT_KINDS|DECLARATION_LIFECYCLE_EXCLUDED_EVENTS|DeclarationsLifecycleExclusion" src/cadrumo --glob '*.py'` -> `pass` (no matches)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (320 exact unused symbols; both target inventories absent)
- `verify:` `vaultspec-core vault check --feature tuimodelo` -> `pass` (0 errors, 4 unrelated warnings)

## Notes

The exact unused-symbol count fell from 322 immediately before S207 to 320 after removal of the two production inventories; the live graph otherwise remained at 65 unreachable modules, 18 orphaned tests, and 2028/2094 shipped modules reachable. The targeted Vaultspec check reported no errors; its four warnings concern a pre-existing extra blank line in a different ADR, a stale feature index, and two retired-step records outside this campaign step.
