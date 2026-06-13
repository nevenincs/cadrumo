---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S05'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02.S05`

Scope: `src/aeat/adapters/outbound/fx/_ecb_refresh.py`.

## Description

- Converted the ECB refresh utility import from absolute `aeat.core` to a package
  relative import.
- Preserved refresh validation behavior.
- Verified touched-file Ruff and structural checks.

## Outcome

The ECB refresh utility no longer contributes to the absolute self-import
baseline.

## Notes

No behavior changes were made.
