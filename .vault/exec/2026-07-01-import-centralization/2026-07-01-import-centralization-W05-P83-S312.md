---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d47ee1c0a2ad0450d79c82c6d3dfbca983a213c6933d70b58dd47a3517b8dee0'
step_id: 'S312'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire the 6 test-only cross-package private import site(s) across 3 test file(s) reaching into `aeat.domain.attachments` onto its promoted top-level facade

## Scope

- `src/aeat/domain/attachments (test consumers)`

## Description

- Run `dev/import_centralization_codemod.py --apply --tests-only` (extended in this Wave with `--include-tests` / `--tests-only` flags reusing the Wave W02 mixed-import, `TYPE_CHECKING`, relative-import, and alias-handling logic) restricted to test modules reaching into `aeat.domain.attachments`.
- Format and lint every touched test file with `ruff check --fix` and `ruff format`.
- Isolate hunks entangled with concurrent peer working-tree edits via a HEAD-anchored `git apply --cached` drive rather than overwriting peer content.

## Outcome

Rewrote all 6 originally-scanned test-only sites across 3 file(s) onto `aeat.domain.attachments`'s promoted top-level facade; `dev/import_hygiene_scan.py` now reports zero test-only cross-package private imports reaching `aeat.domain.attachments`. `pytest --collect-only -q` stayed clean immediately after landing.

## Notes

None.
