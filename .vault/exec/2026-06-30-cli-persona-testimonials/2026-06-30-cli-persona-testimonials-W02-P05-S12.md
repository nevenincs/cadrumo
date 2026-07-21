---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S12'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Audit active-profile label-to-UUID normalization at the CLI root

## Scope

- `src/aeat/entrypoints/cli/__init__.py`

## Description

- Route active-profile UUID normalization through lifecycle-aware profile
  resolution.
- Refuse tombstoned UUIDs for live app commands whether supplied through
  `AEAT_ACTIVE_PROFILE`, the active-profile pointer, or explicit profile input.
- Preserve explicit inspect commands after stale active-profile review.

## Outcome

Commit `5083d57e6` fixed the live app tombstoned UUID bypass. Re-review found it
blocked explicit inspect commands when the stale active profile pointed at a
tombstoned UUID; commit `3a451a94` narrowed the bypass to explicit
`config profile show <label|uuid>`, and commit `e7482b35` kept command-local
options from masquerading as an explicit target. Live app commands remain
refused.

## Notes

Final profile verification reported 55 integration tests passed plus 13 workflow
resolver tests passed.
