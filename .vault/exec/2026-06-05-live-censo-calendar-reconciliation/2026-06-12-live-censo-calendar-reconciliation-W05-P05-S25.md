---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S25'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S25 - evidence-backed AEAT acceptance and canonical taxpayer matching

## Description

- Prevent a bare `aeat_accepted = true` filing record from rendering as AEAT `accepted` in the overview calendar unless it also carries an external evidence reference.
- Canonicalize taxpayer identity matching for calendar justificante metadata, filed-declaration observations, external-import justificante binding, and cross-period justificante matching.
- Add focused regressions for the calendar projection, external import, and cross-period gates.

## Outcome

The calendar no longer treats a local filing record's bare AEAT-accepted boolean as a real AEAT submission signal. A local record still needs an external evidence reference before it can project `accepted`; it still needs matching persisted justificante metadata before it can project `justificante_verified`.

Taxpayer identity matching now trims and uppercases both sides across the relevant gates. This preserves wrong-taxpayer refusals while avoiding false mismatches from casing drift in AEAT/profile metadata.

## Verification

- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/modelo/_external_import_actions.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py` passed.
- `uv run pytest src/aeat/application/overview/tests/test_calendar.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q` passed with 121 tests.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m integration -q` passed with 9 tests.
- `vaultspec-code-reviewer` reviewed S25 and reported no findings. The reviewer noted a missing exact cross-period fixture for bare AEAT acceptance without external evidence; that fixture was added and the gate was rerun before closeout.

## Notes

This step did not rerun live AEAT reads. The previous S24 live run remains the latest authenticated live evidence in this worktree: censo G313 refused with no readable censo, filed and expedientes `pull` bulk reads succeeded with no declarations, notifications persisted one live message snapshot, and justificante pull for Modelo 303 2026 1T refused because no filed declaration existed.
