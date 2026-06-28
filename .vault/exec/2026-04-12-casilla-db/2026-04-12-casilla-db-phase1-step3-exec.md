---
tags:
  - "#exec"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-plan]]"
---

# casilla-db phase1 step3

Wired the `aeat casillas` command group into the root CLI.

- Created: `src/aeat/entrypoints/cli/casillas.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_smoke.py`

## Description

Implemented `list`, `verify`, `extract`, and `translate`. The provider-backed
draft commands now fail clearly with an issue-21 dependency message instead of
pretending to generate live drafts on this branch.

## Tests

CLI tests cover command registration, verification failures for unreviewed
catalogues, JSON listing, and the dependency-gated extract/translate behavior.
