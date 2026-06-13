---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S45'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P12.S45 - addressing round-trip coverage

Scope: cover visible-target, exact-id, and revision-pick round trips through the centralized addressing facade with real repositories.

## Description

- Add `src/aeat/application/modelo/test_work_addressing.py`.
- Exercise `ModeloVisibleFilingTarget` and `ModeloExactWorkUnitTarget` through the public `aeat.application.modelo` facade.
- Verify both target forms resolve to the same authoritative work-unit id in persisted repository state.
- Verify visible work projection returns human-readable modelo, year, period, short id, and exact id metadata.
- Verify explicit calculation-revision id selection returns the owning work-unit id and explicit selector metadata.
- Verify verify, file, and export defaults select command-specific revisions rather than a generic latest revision.

## Outcome

The centralized addressing facade now has real persisted round-trip coverage for the exact id linkage that the CLI will consume: visible filing target to work-unit id, exact work-unit id to visible projection, and revision pick to calculation revision id plus owning work-unit id.

## Notes

Verification commands passed:

- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py src/aeat/application/modelo/test_work_addressing.py -q`
- `uv run --no-sync ruff check src/aeat/application/modelo/_selectors.py src/aeat/application/modelo/_work_addressing.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_work_addressing.py src/aeat/application/modelo/test_selectors.py`
- `uv run --no-sync vaultspec-rag search "modelo calculation revision selector current latest draft latest verified filed explicit" --type code --language python --max-results 12 --port 8766 --json`

The tests use the project isolated runtime profile and real work-unit and calculation-revision repositories. They do not use fakes, mocks, monkeypatches, skips, or xfails.
