---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:f353607467f7ec9514f6b58e48f3795eac0d697624da8540e96cfd9df0a3e8f3'
step_id: 'S42'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Document the full release checklist joining versioning, wheel build, name claim, grant and plugin/marketplace push in RELEASING.md

## Scope

- `RELEASING.md`

## Description

- Document the full per-release checklist joining release-please versioning (including the `packaging/aeat_data` synced-version bump), the packaging-smoke and plugin-validate gates, the human-only push, both publishes, the plugin/marketplace regeneration + push, and the docs update hook.
- Record the deliberate out-of-scope items: Trusted Publishing (needs CI — operator-level policy decision) and any live AEAT interaction.
- Commit `3ebe536354`.

## Outcome

- One document carries the whole release lane end to end.

## Notes

Executed inline by the coordinator during the account rate-limit window.
