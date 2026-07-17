---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S351'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 6 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.adapters.outbound.llm` onto its promoted top-level facade

## Scope

- `src/aeat/adapters/outbound/llm (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.adapters.outbound.llm`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 6 originally-scanned test-only sites across 2 file(s) onto `aeat.adapters.outbound.llm`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.adapters.outbound.llm`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
