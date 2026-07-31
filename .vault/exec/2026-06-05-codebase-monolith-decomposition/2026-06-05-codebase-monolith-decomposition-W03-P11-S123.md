---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:4f535ec4102cb95b5a30376a33336e01a50e27401a7f7057e7634447506946bc'
step_id: 'S123'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P11.S123 Overview Calendar Extraction

Scope: decompose overview application root by calendar and filing summary services behind the overview facade.

## Description

- Extracted overview calendar DTOs, calendar-event synthesis, filing-evidence merge, applicability filtering, profile completeness warnings, and `build_overview_calendar` into `src/aeat/application/overview/_calendar.py`.
- Kept `src/aeat/application/overview/__init__.py` as the public facade for CLI and application consumers.
- Preserved the existing `derive_modelo_applicability` re-export through the overview package boundary.
- Left status-report advisory helpers in the root because they are not part of the calendar aggregation substrate.

## Outcome

`src/aeat/application/overview/__init__.py` is reduced from 1489 lines to 239 lines. The new calendar module is 1239 lines and remains under the current hard module budget.

## Notes

No CLI behavior or calendar semantics changed; this was a mechanical extraction behind the existing facade.
