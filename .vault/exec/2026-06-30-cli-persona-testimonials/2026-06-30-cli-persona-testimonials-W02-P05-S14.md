---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S14'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Sweep profile identity CLI journeys for by-id and by-label parity

## Scope

- `src/aeat/entrypoints/cli/tests`

## Description

- Add real CLI coverage for tombstoned profile UUID and label parity.
- Cover explicit `--profile <uuid>` refusal for tombstoned profiles.
- Cover stale tombstoned active-profile env and pointer behavior while preserving
  explicit `config profile show <label|uuid>`.

## Outcome

Commits `e6c0295`, `5083d57e6`, `3a451a94`, and `e7482b35` added and corrected
profile CLI journey coverage in `src/aeat/entrypoints/cli/tests`. The final
behavior refuses tombstoned UUIDs for live app routing, preserves explicit
profile inspection by label or UUID, and keeps no-arg `config profile show`
active-profile dependent when command-local options are present.

## Notes

Final profile verification passed 55 integration tests across profile lifecycle
and active-profile env override suites.
