---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P01.S03'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P01.S03`

Verified `src/aeat/entrypoints/cli/registry.py` carries no reference
to the renamed doctor app or its mount string and requires no edits.

## Description

A repo-scoped grep over `src/aeat/entrypoints/cli/registry.py` for
the token `doctor` returns no matches. The registry CLI module
exposes the read-only registry verification surface
(`inspect`, `verify`, `audit-oracles`, `verify-filed-state`,
`workbooks verify`, `parity run`, `parity replay`) and never names
the diagnostics Typer app. No edit was required.

## Tests

No behavioural change in this step; the grep gate is the verification.
