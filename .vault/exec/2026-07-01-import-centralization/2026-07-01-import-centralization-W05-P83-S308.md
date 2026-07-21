---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S308'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 12 test-only cross-package private import site(s) across 7 test file(s) reaching into `aeat.domain.submission` onto its promoted top-level facade

## Scope

- `src/aeat/domain/submission (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain.submission`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 12 originally-scanned test-only sites across 7 file(s) onto `aeat.domain.submission`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.domain.submission`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
