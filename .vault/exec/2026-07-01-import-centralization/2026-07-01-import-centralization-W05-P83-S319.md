---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:e0b4e6c3b98f578aefec6127b4b2156735d4623023535fda93785cd8552d1579'
step_id: 'S319'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 1 test-only cross-package private import site(s) across 1 test file(s) reaching into `aeat.domain.calculations.registry.tests` onto its promoted top-level facade

## Scope

- `src/aeat/domain/calculations/registry/tests (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain.calculations.registry.tests`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote the resolvable subset of the 1 originally-scanned sites across 1 file(s) onto `aeat.domain.calculations.registry.tests`'s promoted top-level facade. A residual 1 site(s) remain because they import symbols not yet promoted to the package's `__all__` facade (a Wave W01 facade-promotion precondition, out of this Step's mechanical-rewrite scope). `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
