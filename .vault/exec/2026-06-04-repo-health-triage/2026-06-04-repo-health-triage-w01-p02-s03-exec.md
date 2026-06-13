---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02.S03`

Scope: `src/aeat/_data/corpus/test_corpus_provenance.py`.

## Description

- Removed the absolute `aeat.core.resources` import statement.
- Used dynamic package resolution through the resource boundary because the
  `_data/corpus` test is collected outside a package context.
- Verified the corpus provenance test still collects and passes.

## Outcome

The relative-import checker is clean for this file without turning bundled data
directories into Python packages, and the focused corpus test passes.

## Notes

The dynamic import is intentional because this directory has no `__init__.py`.
