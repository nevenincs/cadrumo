---
tags:
  - '#plan'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
tier: L2
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-research]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---



# `cli-workflow-redesign` `config repair shape` plan

Rename the diagnostics-and-maintenance namespace under `aeat config` from
`doctor` to `repair`, enforce a Pydantic-level always-actionable contract
on every diagnostic row, and add a `reset-state --yes` subcommand that
closes the recovery gap a `WorkflowState` envelope shape drift opens up.
The authorising ADR is the `config repair shape` ADR in `related:`;
this plan executes its `Implementation` section step-by-step.

## Proposed Changes

The redesigned namespace becomes `aeat config repair` with subcommands
`connectivity`, `integrity`, `list`, `quarantine`, `reset-state`, and
`logs`. The bare invocation runs the composite health report. Every
`DiagnosticCheck` whose status is `fail` or `warn` MUST populate either
`next_action` (an exact `aeat ...` command string) or `dead_end` (a short
reason no automated route exists); the constraint is a Pydantic
discriminated-union contract, not a runtime convention. The new
`reset-state` subcommand drops the single unreadable `WorkflowState`
secure-object envelope and emits a `workflow_state.reset` bucket event.
The historical `aeat config doctor` namespace, its Typer app, its locale
strings, its tests, and its references in help text are removed without
compatibility aliases per the no-backwards-compat mandate.

The plan does not introduce any new business logic in `application/` or
`domain/`. It rewires existing diagnostic builders, adds one focused
secure-object delete-and-event flow, and renames the entrypoint Typer app.

## Steps

### Phase `P01` - rename namespace from doctor to repair

Rename the diagnostics Typer app, its mount points, its source module,
and every CLI-emitted reference. No compat alias is introduced.

- [x] `P01.S01` - rename Typer app and module from `doctor` to `repair`; `src/aeat/entrypoints/cli/_config/doctor.py`.
- [x] `P01.S02` - rewire `aeat config` to mount `repair` in place of `doctor`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P01.S03` - update CLI registry entries for the renamed app; `src/aeat/entrypoints/cli/registry.py`.
- [x] `P01.S04` - update help text and command summaries to reference `aeat config repair`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P01.S05` - delete obsolete `doctor` test module and replace with `repair` mirror; `src/aeat/entrypoints/cli/_config/test_doctor.py`.
- [x] `P01.S06` - confirm no surviving `doctor` symbol or string remains in `src/aeat/entrypoints/cli/`; repo-wide grep gate in CI.

### Phase `P02` - enforce always-actionable diagnostic row contract

Promote `DiagnosticCheck` to a discriminated union so silent failing rows
are unreachable by construction.

- [x] `P02.S01` - add `dead_end: str | None` field and validator forbidding both `next_action` and `dead_end` simultaneously; `src/aeat/application/diagnostics.py`.
- [x] `P02.S02` - add model validator requiring exactly one of `next_action` or `dead_end` whenever status is `fail` or `warn`; `src/aeat/application/diagnostics.py`.
- [x] `P02.S03` - add a typed contract test asserting `ValidationError` on a fail row missing both fields; `src/aeat/application/test_diagnostics.py`.
- [x] `P02.S04` - update the text renderer to emit `next: ...` for `next_action` and `note: ...` for `dead_end`; `src/aeat/application/diagnostics.py`.
- [x] `P02.S05` - update the JSON renderer to surface both `next_action` and `dead_end` fields explicitly through `_emit`; `src/aeat/entrypoints/cli/_config/repair.py`.

### Phase `P03` - implement reset-state subcommand and event

Add the recovery route the testimonial flow needs. Scope is exactly the
single `WorkflowState` envelope.

- [x] `P03.S01` - add `reset_workflow_state` application service that deletes namespace `aeat.workflow` key `state` and returns a fingerprint payload; `src/aeat/application/workflow/_persistence.py`.
- [x] `P03.S02` - add `workflow_state.reset` to the bucket event taxonomy with payload schema covering envelope fingerprint and actor metadata; `src/aeat/application/workflow/_events.py`.
- [x] `P03.S03` - emit `workflow_state.reset` in the same logical transaction as the delete; `src/aeat/application/workflow/_persistence.py`.
- [x] `P03.S04` - add `aeat config repair reset-state` Typer command with `--dry-run` and mandatory `--yes`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P03.S05` - reject the command without `--yes` through `CliRefusedBoundaryError`; `src/aeat/entrypoints/cli/_config/__init__.py`.
- [x] `P03.S06` - cover dry-run fingerprint, yes-required gating, and post-reset empty-state load in CLI tests; `src/aeat/entrypoints/cli/_config/test_repair_reset_state.py`.
- [x] `P03.S07` - update `operator_surface` backend contract (`required_children` + diagnostics family) and root/config help documents from `doctor` to `repair` so the apex contract grid matches the live CLI surface; `src/aeat/application/operator_surface/_contract.py`, `src/aeat/application/operator_surface/_help.py`.

### Phase `P04` - wire fail rows to concrete next actions

Populate `next_action` and `dead_end` on every diagnostic the redesign
produces, per the ADR mapping table.

- [x] `P04.S01` - set `next_action` on the `secure_state.load` fail branch to `aeat config repair reset-state --yes`; `src/aeat/application/diagnostics.py`.
- [x] `P04.S02` - set `next_action` on the `secure_objects.integrity` warn/fail branch to `aeat config repair quarantine --yes`; `src/aeat/application/diagnostics.py`.
- [x] `P04.S03` - set `next_action` on the `profile.readiness` fail branch to `aeat config init --tax-id ... --activity ...`; `src/aeat/application/diagnostics.py`.
- [x] `P04.S04` - set `next_action` on the `auth.readiness` fail branch to `aeat config auth setup`; `src/aeat/application/diagnostics.py`.
- [x] `P04.S05` - set `dead_end` on the `registry.load` fail branch with reason that registry is bundled; reinstall aeat; `src/aeat/application/diagnostics.py`.
- [x] `P04.S06` - set `dead_end` on the `environment.python` fail branch with reason upgrade Python; `src/aeat/application/diagnostics.py`.
- [x] `P04.S07` - drop the textual recovery hint embedded in `WorkflowError` raised by `workflow_state_repository().load` since the diagnostic row now owns recovery guidance; `src/aeat/application/workflow/_persistence.py`.

### Phase `P05` - update locale strings and operator-facing copy

Replace `doctor` with `repair` across translatable strings; flip the
shouty `REFUSED` boundary label to sentence case per the apex tone
contract.

- [x] `P05.S01` - replace `doctor` references with `repair`; `src/aeat/locales/en.yml`.
- [x] `P05.S02` - replace `doctor` references with `repair`; `src/aeat/locales/es.yml`.
- [x] `P05.S03` - replace `doctor` references with `repair`; `src/aeat/locales/ca.yml`.
- [x] `P05.S04` - replace `doctor` references with `repair`; `src/aeat/locales/hu.yml`.
- [x] `P05.S05` - replace the all-caps `REFUSED:` prefix in the boundary text renderer with sentence-case `Refused.`; `src/aeat/entrypoints/cli/_errors.py`.
- [x] `P05.S06` - update the locales CLI string table to match the renamed namespace and sentence-case boundary label; `src/aeat/locales/cli.py`.

### Phase `P06` - cross-document and registry sweep

Land the rename across the rest of the source tree so no `doctor`
reference survives in code, tests, or `--help` output.

- [x] `P06.S01` - update CLI wizard command suggestions that point at the old doctor namespace; `src/aeat/application/wizard/_commands.py`.
- [x] `P06.S02` - update error-registry messages that name `aeat config doctor` in their hint text; `src/aeat/core/errors/_registry.py`.
- [x] `P06.S03` - update error-registry domain hints that name `aeat config doctor`; `src/aeat/core/errors/registry/_domain.py`.
- [x] `P06.S04` - update the live-app CLI module references to the renamed namespace; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `P06.S05` - update the CLI common emitter docstrings and prompt strings; `src/aeat/entrypoints/cli/_common.py`.
- [x] `P06.S06` - grep the repo for surviving `config doctor` or `aeat doctor` mentions and either rename them or document why they survive as historical fixtures; repo-wide CI gate.

### Phase `P07` - resolve code-review findings

Resolve the six findings raised by the `P301` code-review audit
(two critical, two high, two medium). Each step lands the production
fix plus the smallest test that proves the fix is on the live path.

- [x] `P07.S01` - move the sentence-case error prefix into the production rendering boundary; introduce `_TEXT_PREFIX` dispatch table in `src/aeat/core/errors/_registry.py` and rewire `render_error_text` to use it; update the `Refused.` and grep-stable assertions in `src/aeat/entrypoints/cli/test_error_boundary_integration.py` and `src/aeat/core/errors/test_registry.py`.
- [x] `P07.S02` - flip the `logging.file` row's `next_action` from `aeat --help` to `aeat config repair logs`; `src/aeat/application/diagnostics.py`.
- [x] `P07.S03` - order the bucket-event emission before the secure-object delete in `WorkflowStateRepository.reset_workflow_state` so the trail survives a downstream failure; add a real-exception-injection test in `src/aeat/application/workflow/test_persistence.py`.
- [x] `P07.S04` - rename the surviving `aeat config doctor` runtime hint and docstrings; `src/aeat/adapters/persistence/storage/sql/secure_objects.py` to `aeat config repair`.
- [x] `P07.S05` - harmonise `_profile_check` and `_auth_check` onto the ADR-canonical `profile.readiness` / `auth.readiness` row names; update `src/aeat/application/test_diagnostics.py` and `src/aeat/application/test_diagnostics_dispatch.py`.
- [x] `P07.S06` - rename `ConfigDoctorReport` / `build_config_doctor_report` / `render_config_doctor_text` to their `…Repair…` form; update every caller and docstring across `src/aeat/application/diagnostics.py`, `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/application/wizard/_status.py`, `src/aeat/core/access_gate/__init__.py`; fold in L-1 by renaming `aeat.test.doctor.rotation` and `doctor-row-N` fixture identifiers in `src/aeat/application/test_diagnostics.py`.

## Parallelization

`P01` blocks every later phase because subsequent phases edit the
renamed module path. `P02` and `P03` are independent once `P01` lands
and may be picked up in parallel. `P04` depends on both `P02` (the
new field shape) and `P03` (the `reset-state` command string must
exist before fail rows can point at it). `P05` and `P06` depend on
`P01` only and may run in parallel with `P02`, `P03`, and `P04` once
`P01` lands.

## Verification

The plan is complete when every Step is closed (`- [x]`) and the
following hold:

- `aeat config repair --help` lists the six subcommands.
- `aeat config repair` (no subcommand) runs the composite report and
  every fail or warn row carries either a `next:` or `note:` line.
- `aeat config doctor` resolves to no command (Typer exits with the
  unknown-command exit code, not an alias redirect).
- Constructing a `DiagnosticCheck` with `status="fail"` and neither
  `next_action` nor `dead_end` raises `ValidationError`.
- `aeat config repair reset-state --yes` deletes the workflow-state
  envelope, emits a `workflow_state.reset` bucket event, and the next
  `aeat config init ...` succeeds.
- `aeat config repair reset-state` without `--yes` exits with the
  refusal exit code and emits no bucket event.
- The literal string `REFUSED` does not appear in the text-rendered
  error envelope; the literal `Refused.` appears once at the head of
  the boundary message.
- Repo-wide grep for `config doctor`, `aeat doctor`, or `doctor =`
  inside `src/aeat/entrypoints/cli/` returns no hits.
- The four locale files contain no `doctor` token.
