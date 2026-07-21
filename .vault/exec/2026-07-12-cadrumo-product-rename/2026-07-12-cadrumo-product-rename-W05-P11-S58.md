---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S58'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget CI source paths and named product jobs

## Scope

- `.github/workflows/ci.yml`

## Description

- Rename the workflow and matrix job display identity to Cadrumo.
- Retarget registry verification and oracle-audit commands to the canonical executable.
- Add structural tests for Cadrumo commands, source paths, labels, and former-product absence.

## Outcome

The primary CI workflow is now `Cadrumo CI`, with a Cadrumo-owned job identifier
and display label across Ubuntu and Windows. Registry validation invokes the
canonical `cadrumo` command, while Semgrep continues to inspect `src/cadrumo`.
Generic cache identities remain tool-owned and require no product rename.

## Notes

Actionlint, direct YAML parsing, Ruff formatting and lint, two real workflow
structure tests, whitespace validation, and the focused former-product residue
gate passed. No authority-owned AEAT term was present on this workflow surface.
Formal review against the committed product-rename ADR found no unresolved
finding.
