---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S363'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.core.decimal` onto its promoted top-level facade

## Scope

- `src/aeat/core/decimal (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.core.decimal`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 1 originally-scanned test-only sites across 1 file(s) onto `aeat.core.decimal`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.core.decimal`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
