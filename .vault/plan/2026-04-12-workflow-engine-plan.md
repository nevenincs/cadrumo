---
name: workflow-engine-plan
description: Implementation plan for the composite end-user workflow engine (issue #59) — ten-stage orchestration, Protocol injection, dry-run-by-default, files-only persistence.
tags:
  - "#plan"
  - "#workflow-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-workflow-engine-research]]"
  - "[[2026-04-12-workflow-engine-adr]]"
---

# workflow-engine plan

## intent

Deliver `aeat.application.workflow` — the project's first composite end-user
command — per the accepted ADR
`[[2026-04-12-workflow-engine-adr]]`. The engine orchestrates the
already-merged deadline / sync / filing / submission components and
Protocol-stubs the in-flight inbox / status / certificate surfaces so
it compiles and tests standalone.

## layout

```
src/aeat/application/workflow/
├── __init__.py              # public facade, re-exports only
├── _errors.py               # WorkflowError / WorkflowAbortedError / WorkflowComponentError
├── _models.py               # pydantic v2 models + enums (WorkflowStage etc.)
├── _protocols.py            # 8 typing.Protocol definitions
├── _engine.py               # WorkflowEngine, run_next, run_for_period
├── _persistence.py          # JSON load/save/list for WorkflowResult
├── _default.py              # default_engine() factory wiring real components
├── test_models.py           # colocated unit tests
├── test_engine.py           # happy path + every abort reason + round-trip
├── test_persistence.py      # files-only roundtrip
└── test_live.py             # single @pytest.mark.live smoke
```

CLI wiring:

```
src/aeat/entrypoints/cli/workflow/
├── __init__.py              # typer sub-app mounted via app.add_typer
├── _helpers.py              # shared printing + run_id resolution
├── next.py                  # aeat workflow next
├── run.py                   # aeat workflow run
├── show.py                  # aeat workflow show <run-id>
├── list.py                  # aeat workflow list [--since]
└── test_workflow_cli.py     # unit tests (typer.testing.CliRunner)
```

## stage-by-stage implementation

1. **models (`_models.py`)**
   - `WorkflowStage(StrEnum)` exact 10 values, ordered as in the ADR.
   - `WorkflowAbortReason(StrEnum)` exact 9 values per the issue.
   - `WorkflowStep` (strict+frozen+extra='forbid'): `stage`,
     `started_at`, `ended_at`, `success`, `summary: Translatable`,
     `details: dict[str, str] | None` (the single sanctioned
     bare-string dict, justified in the ADR).
   - `WorkflowResult` (strict+frozen+extra='forbid'): `run_id`,
     `started_at`, `ended_at`, `final_stage`, `aborted_reason`,
     `obligation_modelo`, `obligation_period`, `draft_id`,
     `submission_id`, `steps: tuple[WorkflowStep, ...]`, `summary:
     Translatable`.
   - `compute_run_id(tax_id, modelo, period, started_at)` → 16-hex
     stable hash (`sha256`).
   - We do NOT embed `FilingObligation` directly in the result so
     the schema stays standalone; we capture its `(modelo, period)`
     projection.

2. **errors (`_errors.py`)**
   - `WorkflowError(AeatError)`.
   - `WorkflowAbortedError(WorkflowError)` — used by callers that opt
     into exception-on-abort; carries the `WorkflowResult`.
   - `WorkflowComponentError(WorkflowError)` — wraps unexpected
     component exceptions before they become `UNHANDLED_EXCEPTION`
     step records.

3. **protocols (`_protocols.py`)**
   - `DeadlineProfileLike` / `FilingDraftLike` / `ObligationLike` —
     structural typing.Protocol shapes so we never hard-import from
     sibling subpackages.
   - `DeadlineEngineProtocol.compute(profile, year, today=None) -> ScheduleLike`.
   - `FilingDraftBuilderProtocol.build(*, modelo, period, profile, inputs) -> FilingDraftLike`.
   - `SubmissionEngineProtocol.preflight(draft, *, today) -> None` and
     `async submit_draft(draft, *, dry_run, override_confirmation, today=None) -> SubmittedFilingLike`.
   - `async SyncRunnerProtocol.run(*, auto_heal=False) -> None`.
   - `StatusReaderProtocol.already_filed(*, tax_id, modelo, period) -> bool` (stub).
   - `InboxProtocol.has_blocking_requerimiento(*, tax_id, modelo) -> bool` (stub).
   - `CertificateBundleProtocol.available() -> bool`,
     `identity() -> str` (stub).
   - `FilingInputsProviderProtocol.load(*, modelo, period) -> Mapping[str, object]`.

4. **engine (`_engine.py`)**
   - `WorkflowEngine` class; stores the 8 protocol handles + settings.
   - `async run_next(profile, *, dry_run=True, override_confirmation=False, sync_first=True, today=None, fail_on_warning=False) -> WorkflowResult`
     — single linear method; one `_run_stage` helper per stage.
     Bailouts return a `WorkflowResult` with `final_stage=ABORTED`
     and a populated `aborted_reason`. Happy path terminates at
     `final_stage=DONE`.
   - `async run_for_period(profile, modelo, period, *, ...)` — skips
     next-obligation selection and targets the named `(modelo,
     period)`; still calls the deadline engine to resolve window
     state for preflight.
   - `UNHANDLED_EXCEPTION` is the catch-all for unexpected component
     errors — stores `details={"exception_type": ..., "exception_repr": ...}`.

5. **persistence (`_persistence.py`)**
   - `save_result(result, *, runs_dir)`, `load_result(run_id, *, runs_dir)`,
     `list_results(*, runs_dir, since=None)`. No globals.

6. **default factory (`_default.py`)**
   - `default_engine(*, settings) -> WorkflowEngine` wires the real
     on-main components (`DeadlineEngine`, `build_draft`,
     `SubmissionEngine`, `LiveSyncRunner`) through thin adapters.
     In-flight stubs (inbox/status/cert) raise
     `NotImplementedError` with a "wire #43/#46/#8 here" message so
     callers are forced to inject their own handles until those land.

7. **CLI (`src/aeat/entrypoints/cli/workflow/`)**
   - Mirrors `src/aeat/entrypoints/cli/submission/`. Four subcommands, each with
     `--json`.
   - `next` and `run` require `--i-understand-this-is-real` alongside
     `--no-dry-run` to enter live mode; otherwise the engine returns
     `USER_CANCELLED` at the `DRY_RUN_SUBMIT` stage.
   - `show` reads JSON via `_persistence.load_result`; `list` walks
     `_persistence.list_results`.

8. **settings + env**
   - `aeat_workflow_runs_dir: Path` default
     `PROJECT_ROOT / "var" / "workflow-runs"`.
   - `aeat_workflow_sync_first_default: bool` default `True`.
   - `aeat_workflow_draft_inputs_path: Path | None` default `None`.
   - Matching three lines in `env/.env.example`.

9. **tests** (all colocated, all `@pytest.mark.unit`, no mocks/patches)
   - `test_models.py`: enum values, pydantic strictness,
     `compute_run_id` stability, JSON round-trip.
   - `test_engine.py`: happy path, one test per abort reason, the
     dry-run default, the explicit-confirmation rule, sync-first
     toggle, `run_for_period`. Real Protocol-conforming test doubles
     only.
   - `test_persistence.py`: save/load/list round-trip, `since` filter.
   - `test_live.py`: single `@pytest.mark.live` test gated via
     `requires_live_enabled()`.
   - CLI tests under `src/aeat/entrypoints/cli/workflow/test_workflow_cli.py`.

## plan review

Reviewed against the ADR. The ten-stage ordering, the bailout
matrix, the one sanctioned `dict[str, str]` exception, the
Protocol-injection strategy, and the files-only persistence all line
up. Every `WorkflowAbortReason` has a planned test. The CLI mirrors
the existing submission surface for uniformity.

**Outcome:** plan approved, proceed to execution.

## execution sequence

1. Add settings + env lines; confirm `test_config.py` still passes.
2. Land `aeat.application.workflow._models`, `_errors`, `_protocols`.
3. Land `_engine.py` + the happy-path engine test.
4. Add one test per `WorkflowAbortReason`, then persistence tests.
5. Land `_default.py` and the CLI subpackage.
6. Wire the new typer sub-app in `aeat.entrypoints.cli.__init__`.
7. Run `just lint`, `just typecheck`, `just test`, `just hooks`.
8. Write exec step records + phase summary.
9. Invoke `vaultspec-code-review` skill, persist the audit.
10. Commit + push + open PR (`Closes #59`).
