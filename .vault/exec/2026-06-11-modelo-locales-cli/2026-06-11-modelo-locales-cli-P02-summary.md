---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# `modelo-locales-cli` `P02` summary

Phase P02 delivered the `python -m aeat.locales modelo` command surface for schema-local translation campaign control.

- Modified: `src/aeat/locales/cli.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `src/aeat/locales/_modelo_manager.py`
- Modified: `src/aeat/locales/__init__.py`

## Description

The locale CLI now exposes modelo-specific `audit`, `scaffold`, `set`, `remove`, and `coverage` commands. These commands route all schema-local translation writes through `ModeloLocaleManager`, leave official schema labels intact, and keep CLI help/diagnostics in the existing eager YAML locale catalogues.

The localized command surface includes Typer help text and translated diagnostics for scaffold writes, no-change scaffold output, set/remove writes, coverage rows, and missing/stale audit drift. Static `tr(...)` call sites are used for the drift diagnostics so the ordinary locale scanner can enroll the keys.

Focused verification passed for touched-module ruff checks, help rendering, complete M130 coverage/audit, incomplete M303 audit drift reporting, and the P02 code review. A fresh top-level locale scaffold check is currently blocked by an unrelated active worktree import regression in `application/filing/_export.py`.
