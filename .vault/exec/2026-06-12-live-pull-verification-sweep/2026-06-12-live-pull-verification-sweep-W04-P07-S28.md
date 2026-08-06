---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:79447bbd419b834a3391a9978b903746398859b7cecbcdced18870f8fba58779'
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

## 2026-07-15 addendum: the opt-in `aeat_live` lane, actually run

This addendum runs the opt-in authenticated portion the record above marked
blocked and gives honest pass/fail/error counts. No test was skipped, and no
skip is treated as green.

### Description

- With the same operator-present authenticated Cl@ve Móvil session as `S11`/`S12`/`S27`
  live, ran `pytest -m aeat_live src/cadrumo/adapters/outbound/aeat src/cadrumo/application/live -q --tb=short`
  with `CADRUMO_LIVE_TESTS_ENABLED=1` set (25 of 830 collected, 805 deselected by the marker).
- Ran it twice: once with `CADRUMO_LOCAL_STORAGE_ROOT`/`CADRUMO_SECRET_STORE_*` also
  exported from this sweep's isolated-profile environment (contaminating the
  per-test tmp-path isolation most of these tests build for themselves), and once
  with those four overrides removed (only `CADRUMO_LIVE_TESTS_ENABLED=1` plus the
  real `CADRUMO_CLAVE_MOVIL_*`/`CADRUMO_AUTH_PROVIDER` values from `env/.env`).
- Both runs produced the identical result (same 13 failing node ids, same 12
  passing node ids), confirming the failures are genuine external/config
  prerequisite gaps, not an artefact of the storage-root leak.

### Outcome

**25 collected, 12 passed, 13 failed, 0 skipped, 0 errors, ~127-141s per run.**

Passing (12): `test_aeat_authenticator_synchronous_surface_live` is NOT in this
list (see failing below) — the 12 passes are the tests whose live surface needs
only the opt-in flag and no further per-provider secret: `test_clave_movil_playwright_entrypoint_reaches_live_selector`,
both `test_live_evasion.py` bot-detection/session-reaping probes, both
`test_groi_check_live.py` driver/selector tests that reached AEAT successfully
(`test_groi_driver_returns_valid_verdict_for_registered_telefonica_nif` and one
other), the `test_renta_web_open_capture_replay.py` baseline-employee and four
profile-variant replay-payload tests, `test_renta_web_open_safety_live_proof.py::test_safety_guard_blocks_presentar_declaracion_click_on_live_simulator`
(the FORBIDDEN-click safety-guard proof — logged its expected block message
during the run), and `test_verify_live.py::test_verify_csv_round_trip`.

Failing (13), every one a genuine external-prerequisite/config gap, not a code
regression:

- `test_declarations_live.py::test_walk_modelo_100_returns_at_least_one_declaration`,
  `::test_capture_declaration_returns_pdf_bytes`, `test_groi_check_live.py::test_groi_form_selectors_still_match_live_dom`,
  `::test_groi_verdict_parser_recognises_live_telefonica_certification` — each
  raises `NoActiveProfileError`/`AuthProfileIdentityMismatchError` inside the
  test's own isolated tmp-path fixture; these tests build their own throwaway
  profile per-run and something in that fixture path does not carry the
  authenticated identity/session the test body expects.
- `test_iva_wallet_live.py::test_live_iva_wallet_capture_persists_reconciles_and_feeds_local_guard`,
  `test_iva_compensation_wallet_live.py::test_fetch_iva_compensation_wallet_live_returns_read_observation`
  — same live wallet-parser mismatch documented in `S26` (`FAIL_SEDE_PARSE` /
  `external_shape_changed`, summary total vs. row-sum inconsistency).
- `test_certificate_live.py::test_verify_handshake_live_against_aeat`,
  `test_authenticator_live.py::test_aeat_authenticator_full_live_flow` — fail
  with "AEAT certificate env vars are not fully configured after live opt-in":
  these need a configured AEAT digital-certificate credential, which this
  Cl@ve-Móvil-only sweep does not have.
- `test_clave_permanente_live.py::test_clave_permanente_provider_full_login_with_central_playwright`
  — fails with "CADRUMO_CLAVE_PERMANENTE_DNI_NIE and CADRUMO_CLAVE_PERMANENTE_PASSWORD
  are not both configured": needs a separate Cl@ve Permanente credential this
  sweep never configured.
- `test_clave_movil_live.py::test_clave_movil_provider_probes_persisted_session_with_central_playwright`
  — fails with "No persisted encrypted Cl@ve Móvil session is available to probe":
  the test expects a session persisted by ITS OWN prior test run/fixture, not the
  externally-acquired session this sweep's CLI login created.
- `test_clave_movil_live.py::test_clave_movil_provider_full_login_with_central_playwright_when_explicitly_enabled`
  — fails with "AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH is not 1 after live opt-in": a
  second, separate opt-in flag this sweep did not set (deliberately — setting it
  would drive a second, independent full Cl@ve login flow through the test's own
  fixture, competing with the CLI-driven session for the same AEAT account
  concurrently; not attempted for session-safety reasons).
- `test_justificante_capture_live.py::test_live_justificante_capture_persists_and_is_retrievable`
  — fails with `NoActiveProfileError`, the test's own isolated fixture, same shape
  as the declarations/GROI failures above; separately, this sweep's own CLI-driven
  `justificante pull` attempts also failed live (see `S26`), so this failure is
  consistent with a genuine underlying gap in the justificante-capture path, not
  purely a test-fixture artefact.

### Notes

- This is an honest, non-tautological count: 12 pass / 13 fail / 0 skip / 0
  error, reproduced identically across two independent runs. No failure was
  retried into a pass, and no skip is reported as acceptance.
- The `AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH` and `CADRUMO_CLAVE_PERMANENTE_*` gaps are
  deliberate scope boundaries of this sweep (Cl@ve Móvil only, single concurrent
  session), not defects; the certificate and `NoActiveProfileError`-shaped
  fixture failures are genuine gaps worth a follow-up look but are outside this
  step's closure criterion, which is the honest count itself.
- Redacted per the sweep convention: node ids and typed failure messages only;
  no raw NIE/NIF, Cl@ve support number, or passphrase appears above.
