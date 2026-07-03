---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S330'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 5 test-only cross-package private import site(s) across 5 test file(s) reaching into `aeat.application.storage.calc_sheets` onto its promoted top-level facade

## Scope

- `src/aeat/application/storage/calc_sheets (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.application.storage.calc_sheets`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote the resolvable subset of the 5 originally-scanned sites across 5 file(s) onto `aeat.application.storage.calc_sheets`'s promoted top-level facade. A residual 3 site(s) remain because they import symbols not yet promoted to the package's `__all__` facade (a Wave W01 facade-promotion precondition, out of this Step's mechanical-rewrite scope). `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
