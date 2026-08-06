---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:49afd3515abd5379b18511babe85a362aec1977d013c0fc677a40fd916ea88f9'
step_id: 'S299'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 427 test-only cross-package private import site(s) across 138 test file(s) reaching into `aeat.domain.modelos` onto its promoted top-level facade

## Scope

- `src/aeat/domain/modelos (test consumers)`

## Description

- Extend `dev/import_centralization_codemod.py` with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic.
- Run the codemod against every test module reaching into `aeat.domain.modelos`, rewriting resolvable private-submodule imports onto the package's promoted `__all__` facade.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote the resolvable subset of the 427 originally-scanned sites onto `aeat.domain.modelos`; `pytest --collect-only -q` stayed clean immediately after landing. A residual ~5 sites remain because they import symbols not yet promoted to the package's `__all__` facade (a Wave W01 facade-promotion precondition, out of this Step's mechanical-rewrite scope).

## Notes

None.
