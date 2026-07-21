---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S03'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden check-aeat-notifications.md

## Scope

- `docs/how-to/check-aeat-notifications.md`

## Description

- Verify-close: read `check-aeat-notifications.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding B3 (`portals list` un-runnable): the page now shows a runnable `aeat app live portals list`, narrowed by `--modelo` OR by `--category` (with the accepted category enum), rather than the invalid `--category sede_modelo` + mutually-exclusive `--modelo` combination.
- Confirm finding M23 (`filed list` mislabelled as non-downloading): the page documents `filed list --modelo --from-year --to-year` as a live AEAT read, with the local views (`list`/`latest`/`view`/`history`) working offline after a profile exists.
- Confirm the live pull verbs show their required args.

## Outcome

- Page verified compliant at HEAD; findings B3 and M23 resolved (2026-06-19 documentation batch). Delta: none required.

## Notes

- All `aeat app live ...` verbs cited resolve against the live surface (conformance gate). CLI conformance gate green.
