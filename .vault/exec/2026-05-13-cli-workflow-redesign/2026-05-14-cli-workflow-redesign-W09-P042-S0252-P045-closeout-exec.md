---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W09.P042.S0252..W09.P045.S0270'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
---

# `cli-workflow-redesign` `W09.P042.S0252` + `W09.P043..P045` closeout

Closed plan rows: `S0252`, and every row of phases `W09.P043`,
`W09.P044`, `W09.P045` (`S0253..S0270`).

## Per-row rationale

### S0252 — boundary inventory entry

Not codified. The retired `aeat.application.profile` package is
fully absent from the working tree as of `2273381e`; an absence
test that asserts deleted paths stay deleted is meta-process state
of the kind the project explicitly rejects (see the
no-transient-meta-in-source memory rule and the user directive on
2026-05-14: "test_legacy_application_profile_imports_have_no_consumers
is a noop"). The architectural enforcement is the deletion itself,
not a perpetual sentinel test in `test_backend_boundary.py`.

### W09.P043 — de-shim and de-stub cleanup

- `S0253` shims: none survived — the legacy package is gone with
  no transitional helper carried into the canonical namespace.
- `S0254` placeholder stubs: none ever existed inside
  `aeat.application.profile`; nothing to remove.
- `S0255` stubbed paths: the canonical `ProfileLifecycleService`
  is the single sanctioned write path. CLI verbs, wizard
  persistence, Google OAuth, and `WorkflowState.active_profile_record`
  call it directly through `application/user_profile/_orchestration`.
- `S0256` deprecated command spelling: every wizard
  `WizardQuestion.profile_key` is now a canonical schema path; CLI
  examples in help text reference canonical paths. The legacy
  spellings (`tax.id`, `output.language`, …) are not aliased in
  `model_selectors` or in CLI normalisation.
- `S0257` shim/stub tests: `application/profile/test_actions.py`
  and `test_validate.py` were removed with the package; the
  canonical equivalents live in `application/user_profile/` and
  exercise real secure-DB persistence.
- `S0258` boundary inventory: same rationale as `S0252` — no
  metastate test added.

### W09.P044 — real behavior verification

The phase is satisfied by the targeted test slice committed
across `1b99d2f0`, `0d2c64a3`, `6437c246`, and `2273381e`:

- `S0259` service contract tests:
  `application/user_profile/test_lifecycle.py` (9 tests covering
  register/edit/remove/duplicate/listing + bounded-payload
  emission).
- `S0260` persistence integration:
  `application/user_profile/test_repository.py` (7 tests)
  exercise `UserProfileLifecycleRepository` and
  `UserProfileSnapshotRepository` against the real secure
  object store.
- `S0261` negative tests: `test_register_rejects_schema_violations`
  asserts the schema validator refuses an under-populated
  register payload; `test_register_refuses_duplicate_profile_id`
  refuses re-registration; the wizard widget validators in
  `application/wizard/_widgets.py` reject untyped values at the
  CLI boundary (covered in `test_widgets.py`).
- `S0262` command behavior:
  `entrypoints/cli/test_config_setter.py`,
  `test_profile_output_language.py`, and
  `test_root_help_shape.py` exercise the canonical CLI verbs
  through `register_minimal_profile` + `set_active_field` /
  `fact_value`.
- `S0263` end-to-end:
  `entrypoints/cli/test_workflow_surface.py::test_config_init_profile_set_deadlines_and_filing_runtime_share_profile_bucket`
  spans config init -> profile set -> deadline calendar -> filing
  runtime over the real profile bucket.
- `S0264` no skips or xfails: targeted slice (`pytest
  src/aeat/application/user_profile/ src/aeat/application/wizard/
  src/aeat/core/i18n/test_output_language.py` minus the unrelated
  translations resolver) returned 194 passed / 0 skipped / 0
  xfailed.

### W09.P045 — thin CLI exposure

The phase is satisfied by the CLI rewire committed in `2273381e`:

- `S0265` accepted command handlers: every retained verb
  (`aeat config profile {list,get,set,unset,status}`,
  `aeat config init`, `aeat config reset`) lives under
  `entrypoints/cli/_config/__init__.py`.
- `S0266` argument parsing isolated: each handler reads typer
  arguments and immediately delegates; no business logic in the
  command body. `_question_for_profile_key` is descriptor lookup,
  not policy.
- `S0267` delegation: handlers route through
  `application/user_profile/_orchestration.set_active_field`,
  `register_active_profile`, `fact_value`, and
  `_projections.record_to_path_values`. No direct repository
  calls.
- `S0268` `_emit` rendering: every CLI surface ends with
  `_emit(ctx, payload, lines)` and accepts `--format json|text`
  at the root.
- `S0269` central error boundary: failures raise
  `CliRefusedBoundaryError` / `CliValidationBoundaryError` which
  the `command_error_boundary` decorator catches before exit;
  schema validation refusals surface through the canonical
  `ProfileSchemaValidationError` -> registered `ErrorCode`.
- `S0270` help vocabulary: every key example in
  `aeat config profile set/get/unset` is a canonical schema
  path; the wizard catalogue's `profile_key` strings are
  canonical; the legacy spellings (`tax.id`, `output.language`,
  …) are not referenced in any retained help string. The
  existing
  `test_manual_ledger_help_rejects_legacy_vocabulary_across_subcommands`
  test pattern enforces this discipline for the ledger surface;
  the user_profile slice's help is verified by the CLI behavior
  tests in `S0262`.

## Phase summary

W09 closes here: `P041`..`P045` all green. The next slice is W10
(`config-cli-profile-surface`) which expands the verb tree to the
full lifecycle CRUD per the apex W74A reconciliation row.

## Guards held

- No metastate codification (absence tests, "removed" sentinels,
  deferred-code markers) added to the boundary inventory.
- The closeout records why each row is satisfied; the rationale
  lives only in this exec record, not in source code or tests.
