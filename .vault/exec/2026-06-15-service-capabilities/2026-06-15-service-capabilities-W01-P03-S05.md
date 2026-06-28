---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S05'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Add config profile capabilities show/set verbs routed through EditProfileSectionCommand

## Scope

- `add a wizard capabilities section`
- `src/aeat/entrypoints/cli/_config`

## Description

- Add `aeat config profile capabilities show` (resolved posture + source per capability) and `... set <capability> <on|off>` (writes the fact via the single-writer profile path); typed payloads + locales; 3 CLI tests.

## Outcome

Operators can review and set per-profile service opt-in/out from the CLI.

## Notes

The wizard capabilities-section offer at profile creation is a deferred nice-to-have (capabilities are settable via `capabilities set`).

