---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W14.P36` summary

Completed the remaining warning-suppressor audit and identified the broad
helpers that should be burned down next.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W14-P36-summary.md`

## Description

The phase confirms that recent exact helpers are not currently hiding new
Modelo 100 or Modelo 200 warnings. The main remaining legal-risk surface is
legacy generic token stripping, especially `optional_or_numeric_token_strip`,
followed by the mixed `axis_token_group` helper.

## Tests

Ran inline `uv run python` probes over real Modelo 100 and Modelo 200 registry
loads.
