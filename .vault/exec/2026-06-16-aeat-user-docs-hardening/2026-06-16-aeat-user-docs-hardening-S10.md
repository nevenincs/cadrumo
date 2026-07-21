---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden filing-calendar.md

## Scope

- `docs/how-to/filing-calendar.md`

## Description

- Verify-close: read `filing-calendar.md` against its 2026-06-18-audit finding M12 and confirm resolution at HEAD.
- Confirm M12 (`overview calendar` refuses on an undocumented `censo.enrolment_unverified` gate while agenda/backlog/explain succeed; the "Before you start" undersold setup): the page now documents `--allow-incomplete` where the command accepts it (agenda/backlog and calendar) so a fresh profile runs, and names the `censo.enrolment_unverified` unresolved-check case explicitly.

## Outcome

- Page verified compliant at HEAD; finding M12 resolved. Delta: none required. CLI conformance gate green.

## Notes

- The calendar-vs-agenda gate difference is documented rather than surprising the reader.
