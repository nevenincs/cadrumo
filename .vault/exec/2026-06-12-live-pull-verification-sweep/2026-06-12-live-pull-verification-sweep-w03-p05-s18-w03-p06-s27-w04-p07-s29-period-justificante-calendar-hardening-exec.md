---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: W03.P05.S18,W03.P06.S27,W04.P07.S29
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
  - '[[2026-06-12-live-pull-verification-sweep-live-auth-blocker-audit]]'
---

# Period Justificante Calendar Hardening

## Scope

This slice verifies the landed `core.Period` stringification changes across the
calendar, filed-history, justificante, external-import, and cross-period filing
evidence surfaces. It also records explicit CLI verb drift tracking: live filed
history remains under `app live filed pull`; `pull-all` remains absent.

## Implementation

- Added plan tracking to keep filed-history acquisition under `pull` and to
  name censo acquisition as `config profile censo pull`, not refresh.
- Added a regression to
  `src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py` proving the
  overview calendar's filed-history loader only marks a stored justificante as
  `justificante_verified` when the real parsed PDF matches the observation's
  modelo, filing year, typed `core.Period`, and taxpayer identity.
- The regression uses the real Modelo 130 justificante fixture and the encrypted
  `FiledDeclaracionObservationStore`. A second observation deliberately points
  at the same stored bytes while claiming `2026 2T`; the calendar keeps that row
  at `submitted_observed` with `justificante_verified=false`.

## Live Evidence

Authenticated status for the isolated live root reported:

- provider `clave_movil`,
- configured/authenticated/available all true,
- active profile registered and ready.

`config profile censo pull` was attempted twice. Both attempts reached AEAT's
Cl@ve Movil non-QR request page and timed out before completion. The second
diagnostic was `20260612T174432Z`, with `failure_mode=auth_completion_timeout`
and `verification_code_present=true`.

After those pending Cl@ve attempts, `app live filed list --modelo 303
--from-year 2026 --to-year 2026` reached auth preflight but AEAT refused a new
Cl@ve Movil request because a prior petition was still pending server-side:
`failure_mode=pending_petition_blocked`, diagnostic `20260612T174527Z`.

The command drift probe remains correct:

- `app live filed pull-all --help` is rejected with `No such command
  'pull-all'. Did you mean 'pull'?`.

The live-root local calendar projection still succeeds without contacting AEAT:

- `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`
  returned seven Modelo deadline rows and one AEAT notification message event.
- Every filing row remained `local=not_ready_to_file`,
  `aeat=not_observed`, `justificante=false`.
- Warning `censo.enrolment_unverified` remained present with fix command
  `aeat config profile censo pull && aeat config profile censo apply`.

## Verification

- `python -m ruff check src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md` passed.
- `python -m pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_local_calendar_filing_evidence_requires_parseable_matching_filed_justificante src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q` passed: 3 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q` passed: 80 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py -q` passed: 32 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_import_flow.py -q` passed: 57 passed.
- `vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md` passed after the plan wording update.

## Open Rows

- `W02.P04.S10` remains open: censo/Modelo 036 could not be positively pulled
  because Cl@ve did not complete during this run.
- `W02.P04.S11` and `W03.P05.S18` remain open for positive live filed-history
  proof because AEAT blocked new Cl@ve petitions after the pending request.
- `W03.P06.S27` remains open for positive live censo/filed/justificante
  projection, but the local calendar projection and negative warning state are
  verified.
- `W04.P07.S29` is further satisfied by focused tests, but the full live sweep
  remains open until authenticated AEAT reads complete and return usable rows.
