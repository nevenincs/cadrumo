---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4c5eff5c1a46d2c20fd3319525944bcb15f25544e93b0df3e02410cf7c5a7af5'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# `dehu-notification-legal-effect` `P04` summary

P04 closed its only Step, S09. Review found and resolved one owner-surface
cross-field invariant: a calendar filing can no longer carry a notification
service state and reach the deemed-service notice path.

- Modified: `src/cadrumo/application/overview/_calendar_models.py`,
  `src/cadrumo/entrypoints/cli/tests/test_calendar_payload_withholds_authenticated_identity.py`,
  and the plan closure row.
- Created: the P04 audit, S09 Step Record, and this phase summary.

## Description

The canonical `OverviewCalendarEvent` model now refuses a non-`MESSAGE` event
with `notificacion_estado_servicio`; the real DTO regression proves that a
filing carrying `RECHAZO_TACITO` raises validation while a message event still
projects its service state. Independent re-review passed.

The direct owner-surface run passed 15 tests, the serial registry
legal/catalogue rerun passed 158 tests, scoped Ruff passed, and `vault check
all` exited zero. The required full target suites and locale scaffold check
were also run with complete logs: their current red signatures were triaged as
unrelated concurrent registry, locale, action-contract, ledger, profile, and
global-ratchet work. This summary makes no full-tree-green claim.
