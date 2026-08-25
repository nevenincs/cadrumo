---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:608548641c6ff2a06430a159fd5a77d2a7c9045ba6f2a580d3b9671a56b4af1a'
step_id: 'S265'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Bring overview.calendar beneath the real output-schema size budget by reducing its returned payload while preserving retrievable operator detail

## Scope

- `src/cadrumo/application/ and src/cadrumo-harness/src/cadrumo_harness/mcp/tests/test_result_size_budget.py`

## Description

Measure the live `overview.calendar` descriptor, replace its expanded legal-entry and observed-event records with actionable summaries, retain filing/censo state needed for triage, and attach the canonical resolved `overview explain` action to every legal row. Preserve event source/reference coordinates and warning fix actions so omitted detail remains retrievable from its owning surface. Keep the 18,000-character budget unchanged.

## Outcome

The verb-specific schema payload falls from 23,394 to 17,520 characters, below the unchanged 18,000-character ceiling. Legal summaries retain modelo, filing year, period, adjusted deadline, user state, censo verification, the three distinct filing/AEAT/justificante axes, and a typed explanation action whose resolved bindings carry both modelo and filing year. Event summaries retain type, date, source, summary, stable reference, status, AEAT state/time, and justificante state. The budget module passes three tests, the focused calendar integration surface passes 22 tests, the unit payload and coverage contracts pass nine tests, and scoped Ruff plus ty pass.

## Notes

Full legal/evidence records remain the application authority; only the list-oriented CLI/MCP result is summarized. Warning rows retain their canonical resolved remediation, including evidence pull coordinates. Formal review identified that modelo alone could make `overview explain` resolve the current year instead of the row's year; the remediation binds `entry.filing_year` as the resolved `year` argument and the focused integration assertion proves `{"modelo": "303", "year": 2025}`. Re-review then caught that `year` also had to be admitted by the canonical `operator.overview.explain` catalogue declaration before the live resolver would accept the binding; the authority and its drift assertion now declare both verdict-context arguments. The repaired focused integration assertion, catalogue contract, schema-budget module, Ruff, and ty pass, and a fresh live descriptor measurement is 17,520 characters. Concurrent commit `a79c17978a` captured most of the summary projection and updated assertions while splitting live payload modules; S265 adds the final enum narrowing and records the complete proof. No budget or shared-envelope allowance was raised.
