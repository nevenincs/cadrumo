---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:b28d6eacfca8a73bbf74cb8487300b34910b7eef707d5e365f23a3404e33d35e'
step_id: 'S305'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 15 test-only cross-package private import site(s) across 10 test file(s) reaching into `aeat.domain.contribuyente` onto its promoted top-level facade

## Scope

- `src/aeat/domain/contribuyente (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain.contribuyente`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 15 originally-scanned test-only sites across 10 file(s) onto `aeat.domain.contribuyente`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.domain.contribuyente`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
