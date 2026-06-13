---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S67'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S67` tutorial natural-key lifecycle rewrite

Step scope: `docs/tutorials/index.md`.

## Description

- Replace remaining pasted-ID lifecycle commands with natural-key modelo, year, and period commands.
- Remove raw work-unit ID and calculation-revision ID examples from the tutorial path.
- Keep internal IDs framed only as audit and support metadata.
- Verify cited educational-doc commands and relative links against the live CLI.

## Outcome

The tutorial now provisions, calculates, verifies, files, and exports Modelo 130 by passing `--modelo 130 --year 2026 --period 1T`. The reader no longer copies a work-unit ID into calculate, a calculation-revision ID into verify or file, or a work-unit ID into export.

Verification passed with `uv run pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

An initial unmarked pytest invocation selected no tests because the project default excludes docs tests. The corrected docs marker invocation selected and passed 29 tests. Existing Click deprecation warnings remain unrelated to this documentation step.
