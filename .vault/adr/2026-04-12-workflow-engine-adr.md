---
name: workflow-engine-adr
description: Architecture decision record for the composite end-user workflow engine — strict ten-stage ordering, dry-run-by-default safety, Protocol-injected components, files-only persistence.
tags:
  - "#adr"
  - "#workflow-engine"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-workflow-engine-research]]"
  - "[[2026-04-12-workflow-engine-plan]]"
---

# workflow-engine adr

## status

accepted (2026-04-12)

## context

issue #59 introduces the project's first composite end-user command. up
until now every subpackage has been a building block. this is the seam.
the engine must compose six in-process components — most merged on main,
two still in flight — and produce one user-facing answer to "what is my
next filing, and can you dry-run it for me?".

## decisions

### 1. ten-stage strict ordering, hard-coded

`WorkflowStage` is an `enum.StrEnum` with exactly ten values, in order:

1. `LOADING_PROFILE`
2. `SYNCING_CATALOGUES`
3. `COMPUTING_DEADLINES`
4. `CHECKING_INBOX`
5. `BUILDING_DRAFT`
6. `VALIDATING_DRAFT`
7. `RUNNING_PREFLIGHT`
8. `DRY_RUN_SUBMIT`
9. `DONE`
10. `ABORTED`

`DONE` and `ABORTED` are terminal. ordering is enforced *in code* by a
single linear method on `WorkflowEngine`; no graph traversal, no DSL,
no orchestration framework. anyone reading the engine reads exactly one
function and sees the whole pipeline top-to-bottom.

**why this matters:** the contract that downstream code (CI, future
schedule jobs, future UI) reads from is the bailout matrix. if the
ordering can drift, the matrix is meaningless. one function = one
contract.

### 2. bailout matrix (the contract)

| stage                | domain abort reasons reachable                                |
| -------------------- | ------------------------------------------------------------- |
| `LOADING_PROFILE`    | — (profile is an already-validated strict pydantic model)     |
| `SYNCING_CATALOGUES` | —                                                             |
| `COMPUTING_DEADLINES`| `NO_PENDING_OBLIGATION`, `DEADLINE_PASSED`                    |
| `CHECKING_INBOX`     | `INBOX_BLOCKING_REQUERIMIENTO`                                |
| `BUILDING_DRAFT`     | `ALREADY_FILED`, `DRAFT_HAS_ERRORS`                           |
| `VALIDATING_DRAFT`   | `DRAFT_HAS_ERRORS`                                            |
| `RUNNING_PREFLIGHT`  | `PREFLIGHT_FAILED`, `CERT_INVALID`                            |
| `DRY_RUN_SUBMIT`     | `USER_CANCELLED`                                              |

`UNHANDLED_EXCEPTION` is the **universal catch-all**: every stage
that performs an external Protocol call funnels unexpected component
exceptions through `_record_unhandled`, which stamps the failing
stage with `success=False` and raises the internal `_AbortError`
with `reason=UNHANDLED_EXCEPTION`. Concretely, it is reachable from
`SYNCING_CATALOGUES`, `COMPUTING_DEADLINES`, `CHECKING_INBOX`,
`BUILDING_DRAFT`, `RUNNING_PREFLIGHT`, and `DRY_RUN_SUBMIT`.
`LOADING_PROFILE` cannot raise it in v1 because the profile is
already a validated pydantic model by the time the engine receives
it; the stage is preserved as a distinct step for audit visibility.

The universal catch-all is deliberate: the contract downstream
consumers read is *"any unexpected component failure surfaces as
`UNHANDLED_EXCEPTION` at the stage where it originated"*. Listing
the reason once in a dedicated paragraph is clearer than repeating
it on every row of the domain matrix.

Every domain `WorkflowAbortReason` in the table above is reachable
from exactly one or two stages and exhaustively tested. The unit
test suite is the executable specification of this matrix; see
`src/aeat/application/workflow/test_engine.py` for the one-to-one mapping.

### 3. dry-run is the default; live requires double confirmation

the engine inherits the submission engine's contract verbatim:

- `dry_run: bool = True` is the API default.
- live submit requires both `dry_run=False` *and*
  `override_confirmation=True` at the API level.
- the CLI requires both `--no-dry-run` and
  `--i-understand-this-is-real` at the command-line level.
- if the caller passes `dry_run=False` without `override_confirmation`,
  the engine aborts at `DRY_RUN_SUBMIT` with `USER_CANCELLED`. it does
  *not* raise — abort reasons are first-class outcomes.

we copy the submission engine's exact kwarg name (`override_confirmation`)
so the gate is uniform across the codebase.

### 4. components are Protocol-injected

`WorkflowEngine` takes seven `typing.Protocol` handles in its constructor:

- `DeadlineEngineProtocol` (#38, on main — adapter wraps `DeadlineEngine`)
- `FilingDraftBuilderProtocol` (#39, on main — adapter wraps `build_draft`)
- `SubmissionEngineProtocol` (#42, on main — adapter wraps `SubmissionEngine`)
- `SyncRunnerProtocol` (#11, on main — adapter wraps `LiveSyncRunner`)
- `StatusReaderProtocol` (#43, **stub only**)
- `InboxProtocol` (#46, **stub only**)
- `CertificateBundleProtocol` (#8, **stub only** — uses
  `aeat.adapters.outbound.aeat.export.LoadedCertificate` shape)

a `default_engine(...)` factory wires the on-main components to their
adapters. tests construct the engine with hand-rolled Protocol-conforming
classes — never mocks, never patches.

**why Protocol injection:** sibling branches `feature-43`, `feature-46`,
and `feature-8` are still in flight. hard imports would either break our
build or require speculative scaffolding in their territory. Protocols
let the engine compile + test standalone today and rebase cleanly when
the real implementations land.

### 5. files-only persistence (v1)

runs are written as JSON under `AEAT_WORKFLOW_RUNS_DIR` (default
`<repo>/var/workflow-runs`). filename: `<run_id>.json`. `aeat workflow
list` enumerates the directory; `aeat workflow show <run-id>` reads a
single file. the storage layer (#10) wires in as a follow-up.

### 6. strict pydantic v2 everywhere

every record in `aeat.application.workflow` is a strict pydantic v2 `BaseModel` with
`model_config = ConfigDict(strict=True, extra="forbid", frozen=True)`:

- `WorkflowResult`
- `WorkflowStep`
- `WorkflowRunRequest` (internal seed for hashing)

closed enumerations are `enum.StrEnum`:

- `WorkflowStage`
- `WorkflowAbortReason`

errors inherit from `aeat.core.errors.AeatError`:

- `WorkflowError` (base)
- `WorkflowAbortedError` (raised only when the caller explicitly opts in
  to exception-on-abort behaviour; the default path returns the result)
- `WorkflowComponentError` (wraps unexpected component exceptions before
  attaching them to a `WorkflowStep`)

#### the one allowed bare-string dict

`WorkflowStep.details: dict[str, str] | None` is the **single** sanctioned
exception to the project pydantic mandate. justification:

- per-stage diagnostics are inherently free-form: a sync stage might
  surface `{"divergences": "3"}`, a draft stage might surface
  `{"finding_count": "7"}`, a preflight stage might surface
  `{"cert_subject": "...", "cert_not_after": "2027-01-15"}`.
- modelling every possible diagnostic shape as a dedicated pydantic
  union would inflate the schema by an order of magnitude for zero
  type-safety win — every field would still be a string round-tripping
  through JSON.
- the field is explicitly typed `dict[str, str]` (not `dict[str, Any]`),
  so the only thing it permits is human-readable string values.
- `WorkflowStep.summary` carries the *structured* user-facing message
  via `Translatable`; `details` is the *diagnostic escape hatch* a
  developer reads when debugging a failing run.

this exception is documented here, mentioned in the workflow `__init__`,
and rejected anywhere else by code review.

### 7. the engine never touches AEAT-side state directly

every call that crosses the AEAT boundary goes through one of the
injected Protocol handles. the engine itself contains no playwright
calls, no HTTP, no certificate handling, no filesystem traversal of
AEAT artefacts. its sole responsibilities are:

- ordering
- bailout decisioning
- step record construction
- result persistence

this keeps the engine reviewable, mockable in the *real-Protocol* sense
the project demands, and re-targetable when (e.g.) the submission engine
gains a non-playwright backend.

### 8. stable run_id hashing

`run_id = sha256(profile.tax_id || modelo || period || started_at_iso)[:16]`.
deterministic for a given seed; tests assert two runs constructed with
the same seed produce the same id. format: 16 lowercase hex chars.

### 9. CLI surface

a new `aeat workflow` typer subcommand group registered the same way the
existing groups are: `app.add_typer(workflow_module.app, name="workflow",
help="...")`. four subcommands:

- `aeat workflow next` → `run_next`
- `aeat workflow run --modelo --period` → `run_for_period`
- `aeat workflow show <run-id>` → reads JSON
- `aeat workflow list [--since <date>]` → enumerates JSON files

every subcommand has a `--json` flag.

## non-goals

- actually filing to AEAT. dry-run only by default; live path is a
  documented escape hatch.
- a web UI.
- multi-profile orchestration.
- post-submit acknowledgement parsing — that's #44 + #46 follow-up.
- modelos other than 130 — inherited from the submission engine.
- persisting via the storage layer (#10) — files only for v1.

## consequences

- positive: the project finally has a single command that says "do my
  taxes". the seam is auditable in one file. the bailout matrix is the
  contract.
- positive: in-flight branches can land in any order without breaking
  the workflow build because every cross-module symbol is Protocol-bound.
- negative: hand-rolled Protocol test doubles are more verbose than
  `mock.MagicMock`. acceptable cost for the no-mocks mandate.
- negative: files-only persistence will need a migration path when #10
  lands. acceptable; the JSON schema is the strict pydantic model so
  the migration is `model_validate_json` → `storage.write`.
