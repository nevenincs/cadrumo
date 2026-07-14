---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S28'
related:
  - "[[2026-06-12-live-pull-verification-sweep-plan]]"
---

# live pytest lane opt-in inventory and W02.P04 S11-S12-S27 status reconfirmation

## Scope

- `src/cadrumo/adapters/outbound/aeat src/cadrumo/application/live src/cadrumo/entrypoints/cli/tests .vault/exec/2026-06-12-live-pull-verification-sweep`

## Description

- Read the plan, its full exec-record history, and the most recent
  `2026-07-12-live-pull-verification-sweep-audit.md` to reconfirm current status
  before touching anything.
- Ran the `aeat_live` pytest lane without the opt-in flag to inventory the skip
  surface (safe, no authenticated AEAT access attempted).
- Re-ran the offline `unit`/`integration` regressions the prior authenticated
  proofs for `W02.P04.S11`, `S12`, and `W03.P06.S27` depend on, against current
  `src/cadrumo` paths, to confirm no regression since the package move off
  `src/aeat`.
- Did not attempt any authenticated Cl@ve Móvil/certificate session or any
  live AEAT pull; `W03.P06.S26` requires the operator present and was not
  attempted per the dispatch brief.

## Outcome

No plan row closes from this pass. The five rows the 2026-07-12 audit named as
genuinely open (`S11`, `S12`, `S26`, `S27`, `S28`) remain open; this record adds
fresh non-authenticated evidence only.

- `S28` (test-gate row): the non-opt-in inventory is now current — `CADRUMO_LIVE_TESTS_ENABLED`
  unset, `-m aeat_live` collected 35 tests, all skipped, 0 failed, 0 errors,
  in 247s. The opt-in authenticated portion of `S28` remains blocked: it
  requires the same Cl@ve Móvil/certificate operator-present session `S26`
  needs, which this dispatch does not attempt.
- `S11`/`S12`/`S27` (backend/CLI/calendar proof rows): reran 188 tests across
  `test_filed_bulk_capture.py`, `test_filed_capture_calculation_history.py`,
  `test_expedientes.py`, `test_cross_period_clean_state.py`, `test_calendar.py`,
  `test_calendar_filing_evidence.py`, and `test_overview_calendar_verb.py` — all
  passed, confirming the local/backend proof documented in the prior exec
  records still holds at current HEAD. The blocker named in those records is
  unchanged: no authenticated AEAT account state with an actual filed
  declaration row has ever been available to prove positive justificante
  enrollment (`S11`), and broader authenticated expediente/calendar sweep
  outcomes (`S12`, `S27`) still need a fresh operator-present session.
- Confirmed the `pull`-only verb-drift guard still holds post-restructure: the
  former `test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all`
  and `test_live_command_tree_rejects_pull_all_and_capture_all_aliases` tests
  moved to `test_app_live_filed_rendering.py` during the branch's file
  restructuring; all 3 tests there pass, no `pull-all` production command
  exists.
- `S26` was not attempted: it is explicitly an operator-present manual sweep
  and this dispatch was instructed not to attempt live authenticated AEAT
  access.

## Notes

- The shipped `src/cadrumo/tests/README.md` still documents the live opt-in
  env var as `AEAT_LIVE_TESTS_ENABLED` and cites `src/aeat/...` paths, while the
  actual gate (`core/_config_live_tests.py`) uses `CADRUMO_LIVE_TESTS_ENABLED`.
  This is a stale-naming residual from the package rename, out of this dispatch's
  scope; flagging it rather than fixing it here.
- No commit accompanies this record: no production, test, or plan-checkbox
  change was made, only a new exec record documenting re-verification and an
  honest non-closure.
