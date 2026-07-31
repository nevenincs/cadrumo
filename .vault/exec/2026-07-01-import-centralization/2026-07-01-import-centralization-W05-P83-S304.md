---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d9a0ae57878c1c74f5eda9d612ad829e3f4e0964c9f9b5ca725952616947d70e'
step_id: 'S304'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 21 test-only cross-package private import site(s) across 12 test file(s) reaching into `aeat.domain.user_profile` onto its promoted top-level facade

## Scope

- `src/aeat/domain/user_profile (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain.user_profile`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 21 originally-scanned test-only sites across 12 file(s) onto `aeat.domain.user_profile`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.domain.user_profile`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
