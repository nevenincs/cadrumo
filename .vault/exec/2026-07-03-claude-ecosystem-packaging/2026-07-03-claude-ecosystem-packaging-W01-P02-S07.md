---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S07'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Align the mcpb manifest license field from 'see repository' to the real Apache-2.0 SPDX expression

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Align the mcpb manifest license field from the stale `"see repository"` to the real `"Apache-2.0"` SPDX expression, matching `pyproject.toml`.
- Commit `ee67a91384`.

## Outcome

- Every distribution manifest states the same publication-ready license.

## Notes

No incidents. No skipped work.
