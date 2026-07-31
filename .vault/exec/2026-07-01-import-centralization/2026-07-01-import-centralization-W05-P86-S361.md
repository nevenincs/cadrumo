---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:5e6983a7baa800e0a7f896bf625b2d6557f20a7029797b97936cf1d26791454b'
step_id: 'S361'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 8 test-only cross-package private import site(s) across 2 test file(s) reaching into `aeat.locales` onto its promoted top-level facade

## Scope

- `src/aeat/locales (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.locales`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote the resolvable subset of the 8 originally-scanned sites across 2 file(s) onto `aeat.locales`'s promoted top-level facade. A residual 8 site(s) remain because they import symbols not yet promoted to the package's `__all__` facade (a Wave W01 facade-promotion precondition, out of this Step's mechanical-rewrite scope). `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
