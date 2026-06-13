---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02.S04`

Scope: `src/aeat/adapters/outbound/fx/_ecb_provider.py`.

## Description

- Converted ECB provider imports from absolute `aeat.core` imports to package
  relative imports.
- Preserved the provider implementation and public surface.
- Verified touched-file Ruff and structural checks.

## Outcome

The ECB provider no longer contributes to the absolute self-import baseline.

## Notes

No behavior changes were made.
