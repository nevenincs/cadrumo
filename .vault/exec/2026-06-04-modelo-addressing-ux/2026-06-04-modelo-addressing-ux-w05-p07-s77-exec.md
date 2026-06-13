---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S77'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P07.S77` Documentation conformance verification

Step scope: docs conformance lane.

## Description

- Run educational documentation command and link conformance checks.
- Run committed CLI reference drift verification.
- Run generated CLI reference command, schema, and retired-surface conformance checks.
- Confirm the regenerated CLI reference lane is green after the natural-key docs and command updates.

## Outcome

Docs conformance passed with 37 tests:

- `src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.
- `src/aeat/entrypoints/cli/test_doc_reference_drift.py`.
- `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.

## Notes

An initial combined run failed the CLI reference drift check for `docs/cli/app.rst` and `docs/cli/index.rst`, reporting a missing `aeat app live filed capture-all` entry. Running the project CLI reference generator against `docs` left no `docs/cli` working-tree diff, and the same docs conformance command then passed.
