---
tags:
  - '#audit'
  - '#calendar-live-filing-integration'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-plan]]'
---

# `calendar-live-filing-integration` Code Review

## REVIEW-001 | LOW | Type-only snapshot imports referenced the wrong ownership surface

`src/aeat/application/overview/__init__.py` originally imported persisted snapshot types from `aeat.application.live` under `TYPE_CHECKING`, while the concrete classes are owned by `aeat.application.live._expedientes` and `aeat.application.live._notifications`. Runtime behavior was not affected because annotations are postponed, but the import path was weaker for static analysis and future re-export changes. Fixed during review by importing the two persisted snapshot types from their defining modules.

Status: resolved.

## REVIEW-002 | INFO | No open high-risk findings after focused review

The overview calendar integration preserves the local-only boundary: it reads persisted bucket-scoped expedientes and notifications snapshots and does not call live-read gates, browser adapters, or AEAT network surfaces. The bulk filed capture command remains under `app live filed`, delegates to the application service, and advertises the read-only/no-submit contract in command help.

Residual risk: actual "all modelos" remote coverage cannot be proven by unit tests or static review because AEAT live form availability and extraction behavior are modelo/year dependent. The implementation reports per-modelo and per-declaration failures instead of implying silent universal success.

Status: accepted residual risk.

## REVIEW-003 | LOW | Incomplete-profile calendars dropped observed live events

Live verification showed that persisted expedientes and notifications snapshots were captured successfully, but `overview calendar --all-profiles` produced zero event rows for profiles whose taxpayer model was undeclared. The early incomplete-profile return preserved the honest no-obligation state but failed to attach already-observed AEAT facts. Fixed by carrying deduplicated `events` through the incomplete return path and adding a focused regression test.

Status: resolved.
