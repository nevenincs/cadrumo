---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:a7bbdfe01c8ff89e31e03d6df87dfbcb418014e13967bf6a6c622a6c3215d3ae'
step_id: 'S314'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 4 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.domain.usage_ratios` onto its promoted top-level facade

## Scope

- `src/aeat/domain/usage_ratios (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain.usage_ratios`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 4 originally-scanned test-only sites across 2 file(s) onto `aeat.domain.usage_ratios`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.domain.usage_ratios`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
