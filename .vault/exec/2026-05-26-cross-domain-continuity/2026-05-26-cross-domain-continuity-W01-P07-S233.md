---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S233'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-INES-7 fix period token notation inconsistency in overview backlog

## Scope

- `M111 surfaces as 2026Q1 while the rest of the system uses 1T`
- `consolidate period rendering through parse_canonical_period output form so backlog and calendar agree`
- `src/aeat/application/overview/`

## Description

Verified at HEAD (no re-implementation): the period-token-notation inconsistency this Step targets is structurally impossible in the overview surface.

- Confirmed the canonical `Period` value object in `core/_period.py` forbids the combined calendar token entirely: its docstring states a combined string such as `2026Q1` is neither an accepted input nor a canonical output, and the only display projection is the space-separated `__str__` form (`2026 1T`).
- Confirmed the overview backlog composes the calendar directly: `build_overview_backlog` in `application/overview/_backlog.py` calls `build_overview_calendar` and returns its `OverviewCalendarEntry` rows verbatim, so a backlog item IS a calendar entry and the two surfaces cannot diverge on period rendering by construction.
- Confirmed both models serialise the period through one typed `Period` field serializer in `application/overview/_calendar_models.py` (`_serialize_period`), so there is a single rendering path.
- Grep-confirmed zero residual `{year}Q{n}` / `Q1`-style token production anywhere under `application/overview/` or `entrypoints/cli/_overview.py`.

## Outcome

Step closed as pre-satisfied at HEAD. Overview backlog and calendar agree on period rendering through the single typed `Period` serializer; no `2026Q1`-form token is produced anywhere.

Own-surface gate green: `test_backlog.py` (6 passed) plus the period-token normalisation unit tests. The `Period` value object's own contract test enforces the space-separated canonical form.

## Notes

RAG queries run: code search "period token canonical rendering overview backlog calendar"; grep confirmation on `parse_canonical_period`, quarter-token production, and `M111` references in `application/overview/`.

Peer-churn distinguished per the full-tree-gate-owner discipline: the integration suite `test_modelo_period_consistency.py` currently shows 6 red rows, but every failure aborts at `_create_profile()` with "Profile creation is missing filing identity details. Add these flags: --entity-type --surnames" — a peer profile-creation contract change on the `modelo work` surface, NOT the overview period-rendering surface this Step owns. Those rows do not exercise the backlog/calendar rendering agreement and are out of this Step's ownership boundary.
