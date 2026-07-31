---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:51c9482d3b9f5fc15b9083eca3b037e3516d430e234f8a8e6c6673c53207afca'
step_id: 'S350'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 12 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.adapters.outbound.aeat.auth` onto its promoted top-level facade

## Scope

- `src/aeat/adapters/outbound/aeat/auth (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.adapters.outbound.aeat.auth`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote the resolvable subset of the 12 originally-scanned sites across 3 file(s) onto `aeat.adapters.outbound.aeat.auth`'s promoted top-level facade. A residual 2 site(s) remain because they import symbols not yet promoted to the package's `__all__` facade (a Wave W01 facade-promotion precondition, out of this Step's mechanical-rewrite scope). `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
