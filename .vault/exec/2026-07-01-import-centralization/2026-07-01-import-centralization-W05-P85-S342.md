---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:e5da2a485a1515e2b31522cc0f576fca068e4d9b745db2521c7fb613a8da87b9'
step_id: 'S342'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 24 test-only cross-package private import site(s) across 15 test file(s) reaching into `aeat.adapters.persistence.storage.master_key` onto its promoted top-level facade

## Scope

- `src/aeat/adapters/persistence/storage/master_key (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.adapters.persistence.storage.master_key`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote the resolvable subset of the 24 originally-scanned sites across 15 file(s) onto `aeat.adapters.persistence.storage.master_key`'s promoted top-level facade. A residual 14 site(s) remain because they import symbols not yet promoted to the package's `__all__` facade (a Wave W01 facade-promotion precondition, out of this Step's mechanical-rewrite scope). `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
