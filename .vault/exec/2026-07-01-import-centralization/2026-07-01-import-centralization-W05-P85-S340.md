---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S340'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 24 test-only cross-package private import site(s) across 21 test file(s) reaching into `aeat.adapters.persistence.storage.crypto` onto its promoted top-level facade

## Scope

- `src/aeat/adapters/persistence/storage/crypto (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.adapters.persistence.storage.crypto`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 24 originally-scanned test-only sites across 21 file(s) onto `aeat.adapters.persistence.storage.crypto`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.adapters.persistence.storage.crypto`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
