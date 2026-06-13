---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S14'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
---

# W02.P04.S14 - live justificante active-snapshot evidence hardening

## Description

- Re-grounded the live justificante, calendar filing semantics, and cross-period clean-state surfaces after the `core.Period` rollout.
- Hardened `register_capture_as_filing_evidence` so only an `ACTIVE` `JustificanteCaptureSnapshot` can stamp a `ModeloRecord` as `AEAT_LIVE_CAPTURE` evidence.
- Added a regression proving a `SUPERSEDED` live capture refuses before saving a justificante, setting `aeat_accepted`, or attaching external evidence.
- Kept `W02.P04.S14` open because this record proves the local backend invariant, not the full authenticated AEAT justificante pull.

## Outcome

The Modelo/calendar evidence boundary now rejects stale live captures before parsing and persistence. A superseded or discarded AEAT capture cannot become the official evidence reference that clears cross-period clean-state blockers or calendar AEAT-submitted state.

Authenticated live setup was retried under an isolated storage root:

- `AEAT_LOCAL_STORAGE_ROOT=.tmp/live-auth-calendar-state`
- `AEAT_SECRET_STORE_BACKEND=file`
- `AEAT_SECRET_STORE_DIR=.tmp/live-auth-calendar-secrets`
- `AEAT_SECRET_PASSPHRASE` set to a local passphrase with at least eight characters

The default local store remained locked under an unknown existing passphrase, so no stale profile was used. The isolated root reported no profiles and no configured auth. `auth providers` succeeded and listed `certificate` and `clave_movil` as implemented. `auth configure --provider clave_movil` refused with the expected prerequisite: create a profile first with a tax ID. `auth test --provider clave_movil` reported the backend available and ready for operator-mediated Cl@ve completion, but not configured or authenticated.

Live censo/calendar proof remains blocked until the operator supplies the NIF/NIE/CIF for the fresh profile so it can match the AEAT authenticated identity.

## Verification

- `uv run vaultspec-rag search --timeout 900 "justificante capture snapshot state active superseded discarded modelo filing evidence calendar"` returned the calendar filing semantics ADR/audit and live justificante reconciliation records.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q` passed with 12 tests.
- `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py` passed.
- `uv run pytest src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 117 tests.
- `uv run aeat --format json config auth providers` passed under the isolated live-auth root.
- `uv run aeat --format json config profile list` passed under the isolated live-auth root and showed no profiles.
- `uv run aeat --format json config auth status` passed under the isolated live-auth root and reported `configured=false`, `authenticated=false`, and next action `aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>`.
- `uv run aeat --format json config auth test --provider clave_movil` passed under the isolated live-auth root and reported backend availability plus required operator completion.

## Open Work

This record does not close `W02.P04.S14`. The remaining acceptance work is an authenticated `pull` run for the actual filed-period justificante, followed by censo/profile/calendar reconciliation using a fresh profile whose tax identity matches the AEAT authenticated identity.
