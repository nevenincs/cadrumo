---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9413dce09deda0bf0566346562c17817b29dbcbb7b59f64b5c090eb75b175b9b'
step_id: 'S309'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 6 test-only cross-package private import site(s) across 6 test file(s) reaching into `aeat.domain` onto its promoted top-level facade

## Scope

- `src/aeat/domain (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 6 originally-scanned test-only sites across 6 file(s) onto `aeat.domain`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.domain`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
