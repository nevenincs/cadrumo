---
name: workflow-engine-phase1-step1
description: Land the strict pydantic v2 schema, Protocols, errors, persistence, and orchestrator for `aeat.application.workflow` with full unit coverage of the bailout matrix and CLI wiring for issue #59.
tags:
  - "#exec"
  - "#workflow-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-workflow-engine-plan]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-workflow-engine-research]]"
---

# workflow-engine phase-1 step-1

## plan reference

Executing `[[2026-04-12-workflow-engine-plan]]` in full. The ADR
`[[2026-04-12-workflow-engine-adr]]` is the source of truth for the
ten-stage ordering, the bailout matrix, the dry-run-by-default /
double-gate contract, and the single sanctioned `dict[str, str]`
exception on `WorkflowStep.details`.

## outputs

- `src/aeat/application/workflow/` subpackage
  - `_models.py` — strict pydantic v2 `WorkflowStep`, `WorkflowResult`,
    `WorkflowStage` (10-value StrEnum), `WorkflowAbortReason`
    (9-value StrEnum), `compute_run_id` stable hash.
  - `_errors.py` — `WorkflowError`, `WorkflowAbortedError`,
    `WorkflowComponentError`, all subclasses of `aeat.core.errors.AeatError`.
  - `_protocols.py` — 8 `typing.Protocol` handles + narrow pydantic
    stubs for in-flight sibling types (`SubmittedFilingLike`,
    `SyncRunSummary`, `ExpedienteLike`, `RequerimientoLike`).
  - `_engine.py` — `WorkflowEngine` driving the ten stages linearly;
    one `_stage_*` method per stage; centralised
    `_record_unhandled` helper; `_AbortError` internal bailout
    signal.
  - `_persistence.py` — files-only save / load / list of
    `WorkflowResult` under `settings.aeat_workflow_runs_dir`.
  - `_adapters.py` — thin adapters wiring the on-main components
    (`DeadlineEngine`, `build_draft`, `SubmissionEngine`,
    `LiveSyncRunner`) to the narrow workflow Protocols;
    `JsonFileInputsProvider`; `default_engine(...)` factory.
  - `__init__.py` — public facade re-exporting only the symbols
    above.
- `src/aeat/application/workflow/test_models.py`,
  `src/aeat/application/workflow/test_engine.py`,
  `src/aeat/application/workflow/test_persistence.py`,
  `src/aeat/application/workflow/test_live.py` — unit + opt-in live coverage.
- `src/aeat/entrypoints/cli/workflow/` — `aeat workflow {next,run,show,list}`
  subcommands wired through `app.add_typer`, plus
  `test_cli.py` exercising the typer surface via `CliRunner`.
- `src/aeat/config.py` + `env/.env.example` — three additive
  settings: `aeat_workflow_runs_dir`,
  `aeat_workflow_sync_first_default`,
  `aeat_workflow_draft_inputs_path`.

## bailout matrix coverage

Every `WorkflowAbortReason` value is reached by at least one
`@pytest.mark.unit` test in `test_engine.py`:

| reason                        | test                                                   |
| ----------------------------- | ------------------------------------------------------ |
| `NO_PENDING_OBLIGATION`       | `test_no_pending_obligation`                           |
| `DEADLINE_PASSED`             | `test_deadline_passed_via_run_for_period`              |
| `INBOX_BLOCKING_REQUERIMIENTO` | `test_inbox_blocking_requerimiento`                   |
| `ALREADY_FILED`               | `test_already_filed`                                   |
| `DRAFT_HAS_ERRORS` (builder)  | `test_draft_has_errors_via_status`                     |
| `DRAFT_HAS_ERRORS` (validate) | `test_draft_has_errors_via_validation`                 |
| `PREFLIGHT_FAILED`            | `test_preflight_failed`                                |
| `CERT_INVALID`                | `test_cert_invalid`                                    |
| `USER_CANCELLED`              | `test_user_cancelled_without_override`                 |
| `UNHANDLED_EXCEPTION`         | `test_unhandled_exception_from_deadline_engine`        |

Happy path and the explicit-confirmation rule for live submit are
additionally covered by `test_run_next_happy_path`,
`test_dry_run_is_default`, and
`test_live_submit_requires_override_confirmation`. Every test
uses hand-rolled Protocol-conforming doubles — no mocks, patches,
or fakes.

## gates

- `just lint` — green.
- `just typecheck` (`ty`) — green, zero diagnostics.
- `just test` — 444 passed, 1 skipped (opt-in live), 16 deselected.
- `just hooks` (`prek`) — all pre-commit hooks pass on the full
  tree.

## risks / follow-ups

- The certificate, inbox, and status-reader Protocol slots remain
  `None`-by-default until #8, #46, and #43 land on main. The
  `default_engine` factory is intentionally structured so those
  slots become required adapter arguments on rebase without a
  public-API break.
- `_adapters.py` hard-imports `aeat.application.filing.FilingDraft` and
  `aeat.application.sync.LiveSyncRunner` and will need a one-line narrowing
  pass when sibling branches rebase (type-ignore comments flag
  the exact spots).
- Persisting runs through the storage layer (#10) is out of scope;
  files-only is documented in the ADR as the v1 contract.
