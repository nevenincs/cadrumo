---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:7e8e1dbd549affd11167f1b676238a2b07d43e9a26fe038d887aa3f6a6a5493e'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W02.P02` summary

Completed proof, live verification, and review closeout for the calendar filing semantics hardening.

- Modified: `src/aeat/application/overview/tests/test_calendar.py`
- Modified: `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`
- Modified: `.vault/audit/2026-06-05-calendar-filing-semantics-code-review-audit.md`
- Created: `.vault/exec/2026-06-05-calendar-filing-semantics/2026-06-05-calendar-filing-semantics-W02-P02-S04.md`

## Description

Wave W02 added real-behavior tests for local filing semantics, AEAT observed submission, stored justificante verification, calendar event promotion, duplicate-expediente isolation, stale artefact-reference refusal, and cross-profile evidence isolation. Focused lint and tests passed, authenticated live AEAT read-only captures succeeded for filed history, expedientes, and notifications, nested JSON payload schemas were tightened, and the code-review audit findings were resolved.
