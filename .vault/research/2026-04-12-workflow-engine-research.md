---
name: workflow-engine-research
description: Research findings for the end-user composite workflow engine that orchestrates deadlines, draft, submission, sync, status, and inbox into one ordered pipeline (issue #59).
tags:
  - "#research"
  - "#workflow-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-workflow-engine-plan]]"
---

# workflow-engine research

## problem

issue #59 introduces the project's first end-user composite command:
`aeat workflow next` — a single entry point that takes an `AutonomoProfile`,
runs ten ordered stages spanning every previously-merged building block, and
returns a strict-pydantic `WorkflowResult`. dry-run is the default; live
submit requires explicit confirmation matching the submission engine.

## existing surfaces (verified on this branch)

| package              | symbol                                          | status                |
| -------------------- | ----------------------------------------------- | --------------------- |
| `aeat.domain.deadlines`     | `DeadlineEngine.compute(profile, year)`         | merged on main        |
| `aeat.domain.deadlines`     | `AutonomoProfile`, `FilingObligation`           | merged on main        |
| `aeat.application.filing`        | `build_draft(...)` → `FilingDraft`              | merged on main        |
| `aeat.application.filing`        | `validate_draft`, `compute_draft_id`            | merged on main        |
| `aeat.adapters.outbound.aeat.export`    | `SubmissionEngine.submit_draft(draft, ...)`     | merged on main        |
| `aeat.adapters.outbound.aeat.export`    | `Preflight.check(draft, today=...)`             | merged on main        |
| `aeat.adapters.outbound.aeat.export`    | `LoadedCertificate` (protocol-stubbed pydantic) | merged on main        |
| `aeat.application.sync`          | `LiveSyncRunner.run(...)`                       | merged on main        |
| `aeat.core.i18n`          | `Translatable`, `Language`                      | merged on main        |
| `aeat.entrypoints.cli._live`     | `requires_live_enabled()`                       | merged on main        |
| `aeat.core.config`        | `Settings` (pydantic-settings)                  | merged on main        |
| `aeat.core.errors`        | `AeatError`                                     | merged on main        |
| `aeat.status`        | —                                               | **not on this branch** |
| `aeat.inbox`         | —                                               | **not on this branch** |
| `aeat.adapters.outbound.aeat.auth.certificate` | —                                            | **not on this branch** (Protocol-stubbed in `aeat.adapters.outbound.aeat.export`) |

## key facts

- the submission engine *already* enforces an `override_confirmation: bool`
  kwarg gate with a settings-level safety belt
  (`aeat_submission_require_human_confirmation`). the workflow engine must
  inherit the same contract verbatim — no second-guessing.
- `submit_draft` is `async`. so are the workflow engine's entry points.
- the existing CLI surface adds typer subcommand groups via
  `app.add_typer(<module>.app, name=...)`. we mirror this exactly.
- `tests/test_config.py` enforces strict alignment between the `Settings`
  model and `.env.example`. every new setting must land in both.
- `aeat.domain.modelos/__init__.py` is currently empty; `AutonomoProfile` lives at
  `aeat.domain.deadlines._models` and is re-exported from `aeat.domain.deadlines`. we
  import it from `aeat.domain.deadlines` (the public facade), not from the private
  module.
- `Translatable` is a TypedDict with optional `es`/`en`/`hu` fields; pydantic
  v2 happily validates a `dict[str, str]` against it as long as keys are in
  the closed set.
- `requires_live_enabled()` is the only sanctioned way to gate live tests;
  the contract memo says no inline `os.getenv` in test bodies.

## constraints from in-flight branches

| branch                              | territory                          | mitigation                                                                 |
| ----------------------------------- | ---------------------------------- | -------------------------------------------------------------------------- |
| feature-15-pytest-only-testing      | `pyproject.toml [tool.pytest]`, conftest | do not touch                                                          |
| feature-14-synthetic-filing-fixtures | tests/fixtures                    | no overlap                                                                |
| feature-8-cert-auth                 | `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate`        | Protocol stub `CertificateBundleProtocol`; reuse `aeat.adapters.outbound.aeat.export.LoadedCertificate` shape |
| feature-43-status-reader            | `src/aeat/status/`                 | Protocol stub `StatusReaderProtocol.fetch_expedientes`                    |
| feature-46-notifications-inbox      | `src/aeat/inbox/`                  | Protocol stub `InboxProtocol`, `Notificacion`-like model                  |

every cross-module symbol the workflow consumes is bound through a
`typing.Protocol`. the engine compiles standalone; on rebase the real
implementations slot in via constructor injection without source changes.

## bailout matrix (from the issue body)

| stage                  | abort reason                       |
| ---------------------- | ---------------------------------- |
| `LOADING_PROFILE`      | `UNHANDLED_EXCEPTION` (validation fails) |
| `SYNCING_CATALOGUES`   | `UNHANDLED_EXCEPTION` (sync raises) |
| `COMPUTING_DEADLINES`  | `NO_PENDING_OBLIGATION`, `DEADLINE_PASSED` |
| `CHECKING_INBOX`       | `INBOX_BLOCKING_REQUERIMIENTO`    |
| `BUILDING_DRAFT`       | `ALREADY_FILED`, `DRAFT_HAS_ERRORS` |
| `VALIDATING_DRAFT`     | `DRAFT_HAS_ERRORS`                |
| `RUNNING_PREFLIGHT`    | `PREFLIGHT_FAILED`, `CERT_INVALID` |
| `DRY_RUN_SUBMIT`       | `USER_CANCELLED` (live without confirmation), `UNHANDLED_EXCEPTION` |

`ALREADY_FILED` is checked at the boundary between `COMPUTING_DEADLINES`
and `BUILDING_DRAFT` — the status reader protocol is consulted right
before the draft is built; if the period is already filed we abort with
`ALREADY_FILED` *before* we burn cycles building a draft.

## open questions resolved during research

- **q:** which stage owns `ALREADY_FILED`?
  **a:** logically `BUILDING_DRAFT` — the check sits at the start of the
  draft stage, gating the call to `build_draft`. recording it under
  `BUILDING_DRAFT` keeps the bailout matrix one-to-one with the stage
  enum.
- **q:** is `inputs` for `build_draft` something the workflow knows how to
  build?
  **a:** v1 reads it from a settings-controlled file path
  (`AEAT_WORKFLOW_DRAFT_INPUTS_PATH`). a `FilingInputsProvider` Protocol
  is injected so tests can hand in synthetic inputs.
- **q:** how does the engine surface a result for the CLI?
  **a:** runs are persisted as JSON under `AEAT_WORKFLOW_RUNS_DIR`.
  `aeat workflow show <run-id>` reads the file back. v1 is files-only;
  the storage layer (#10) wires in later.

## test strategy

unit tests (`@pytest.mark.unit`) colocated under `src/aeat/application/workflow/`.
every `WorkflowAbortReason` gets at least one dedicated test that:

1. constructs real Protocol-conforming test doubles (no mocks/patches);
2. arranges the doubles to provoke exactly that failure;
3. runs the engine via `asyncio.run`;
4. asserts the resulting `WorkflowResult.aborted_reason` equals the
   target reason and `final_stage` matches the bailout matrix.

happy path: every double returns clean output, the engine reaches `DONE`,
the result has populated `obligation`, `draft_id`, `submission_id`.

stable hash: two runs with the same `(profile.tax_id, modelo, period,
started_at)` produce the same `run_id`.

JSON round-trip: `WorkflowResult.model_dump_json()` re-validates via
`WorkflowResult.model_validate_json(...)` losslessly.

one opt-in `@pytest.mark.live` test wired through `requires_live_enabled()`.
