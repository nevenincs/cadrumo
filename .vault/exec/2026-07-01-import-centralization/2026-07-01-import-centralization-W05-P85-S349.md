---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:33eb76d03b806aeb75e2f19c857564ef8357de7ba955bc6aeefc03de1525a64a'
step_id: 'S349'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 7 test-only cross-package private import site(s) across 4 test file(s) reaching into `aeat.adapters.persistence.storage` onto its promoted top-level facade

## Scope

- `src/aeat/adapters/persistence/storage (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.adapters.persistence.storage`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 7 originally-scanned test-only sites across 4 file(s) onto `aeat.adapters.persistence.storage`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.adapters.persistence.storage`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
