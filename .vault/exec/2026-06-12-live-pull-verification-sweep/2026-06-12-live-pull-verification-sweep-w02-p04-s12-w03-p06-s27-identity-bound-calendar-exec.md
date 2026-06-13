---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S12'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
---

# W02.P04.S12 / W03.P06.S27 - identity-bound expedientes calendar projection

## Description

- Re-grounded calendar filing semantics with `vaultspec-rag search --timeout 900` against the accepted local-filing versus AEAT-submission ADR.
- Bound live expedientes captures to the authenticated AEAT identity by persisting `authenticated_identity` on `ExpedientesCapture` and `PersistedExpedientesSnapshot`.
- Projected expedientes filing events into the overview calendar only when the snapshot identity matches the active profile tax ID supplied by the CLI.
- Kept the identity as an internal trust field on `OverviewCalendarEvent`; it is excluded from JSON output while still gating evidence projection.

## Outcome

The profile calendar no longer treats an AEAT declaration-register row as that profile's submitted filing event when the persisted expedientes snapshot has no authenticated identity or a different identity. This closes a local trust gap between raw AEAT register observations and profile-bound calendar filing state:

- Correct identity: filing event can appear and can contribute `submitted_observed` evidence.
- Wrong or missing identity when a profile tax ID is known: filing event is not projected for that profile and cannot become filing evidence.
- Notifications remain projected as message events because they are not Modelo filing evidence.

This record does not close the live authenticated expedientes or calendar rows. The actual AEAT `pull` run still requires a fresh profile whose tax ID matches the operator-authenticated AEAT identity.

## Verification

- `uv run vaultspec-rag search --timeout 900 "calendar modelo filing local ready aeat submitted justificante verified evidence state calendar event"` returned the accepted calendar filing semantics ADR and related exec records.
- `uv run pytest src/aeat/application/live/tests/test_expedientes.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 91 tests.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/live/tests/test_expedientes.py src/aeat/application/overview/tests/test_calendar.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 133 tests.
- `uv run ruff check src/aeat/application/live/_expedientes.py src/aeat/application/live/__init__.py src/aeat/application/live/tests/test_expedientes.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` passed.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md` passed.

## Open Work

`W02.P04.S12` and `W03.P06.S27` remain open because this is local/backend hardening, not authenticated AEAT proof. The next live proof must create a fresh profile, configure auth, run expedientes/censo/filed/justificante `pull` commands with the operator present, and record exact authenticated outcomes.
