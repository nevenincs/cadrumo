---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
---



# `cli-workflow-redesign` adr: `config doctor shape` | (**status:** `superseded by [[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]`)

> Superseded by the `config repair shape` ADR. The `doctor` namespace is
> replaced by `aeat config repair`: same composite-diagnostics surface,
> renamed to plain operator vocabulary, with two contract additions —
> every diagnostic row must populate `next_action` or an explicit
> `dead_end` reason, and a new `reset-state --yes` subcommand exists to
> recover from `WorkflowState` envelope shape drift. The grammar below
> is retained only as historical record; see the repair-shape ADR for
> the accepted shape.

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The redesigned CLI root is constrained to exactly:

```text
aeat config
aeat app
```

Diagnostics need one stable home. Current implementation already mounts
`aeat config doctor`, and its backend can produce aggregate config diagnostics
and secure-object integrity results. At the same time, browser health exists as
an orphaned package using legacy `--json`, while doctor subcommands have
inconsistent JSON behavior.

Storage maintenance must not become app-scoped command surface. Persisted
maintenance actions, such as quarantine, are bucket-affecting mutations and
must be bucket-scoped with events.

## Considerations

The diagnostics service checks runtime readiness,
registry loading, workflow state, setup/profile/auth readiness, and encrypted
secure-object readability. Browser health exists, but it is outside the root
contract and uses obsolete output semantics.

Secure-object quarantine is a bucket-scoped maintenance operation with bucket
event history.

## Constraints

- Root command shape remains exactly `aeat config` and `aeat app`.
- Storage diagnostics and storage maintenance belong under `aeat config`.
- No app-scoped bucket, quarantine, or storage-maintenance commands are
  introduced.
- Every redesigned command supports `--format json` through `_emit`.
- Legacy `--json` is not retained.
- Every persisted mutation is bucket-scoped and emits a bucket event.
- Compatibility aliases and shims are not allowed.

## Implementation

`aeat config doctor` owns diagnostics for the redesigned CLI.

The accepted grammar is:

```text
aeat config doctor [--format json|text]

aeat config doctor connectivity
    [--target browser|auth|sede|all]
    [--format json|text]

aeat config doctor integrity
    [--namespace NAMESPACE]
    [--format json|text]

aeat config doctor list <namespace>
    [--all|--unreadable]
    [--format json|text]

aeat config doctor quarantine
    [--namespace NAMESPACE]
    [--dry-run]
    --yes
    [--format json|text]

aeat config doctor logs
    [--lines N]
    [--format json|text]
```

Every redesigned doctor command supports `--format json` through `_emit`.

`connectivity` absorbs browser health and future adapter probes.

`integrity` owns secure-object integrity scans.

`list` provides secure-object inventory and drill-down.

`quarantine` is the only accepted persisted mutation in the current design.

`logs` remains part of `config doctor`, but emits both text and structured JSON
through `_emit`.

Read-only diagnostics emit no bucket events.

Persisted diagnostics mutations are bucket-scoped and emit events in the same
logical transaction.

Required event for current quarantine behavior:

```text
secure_object.quarantined
```

The event payload includes bucket id, namespace, count, affected object refs or
row ids, quarantine target, command context, actor/source, and timestamp.

Future events are allowed only when their backends exist:

```text
secure_object.restored_from_quarantine
secure_object.repaired
```

`secure_object.repaired` requires a real repair or rewrap backend.

## Rationale

Diagnostics are configuration and storage health concerns, not operational tax
workflow actions. Keeping them under `config doctor` preserves the two-root
contract while making the existing backend integrity probes discoverable.

Absorbing browser health into `config doctor connectivity` avoids a third root
and removes obsolete `--json` behavior. Keeping quarantine under doctor also
prevents storage maintenance from leaking into `app`, where normal operator
workflow should be ledger/modelo oriented.

The accepted grammar keeps base summary, connectivity, integrity, inventory,
quarantine, and logs separate enough to test and render cleanly while sharing a
single output contract.

## Consequences

Browser health implementation moves behind `aeat config doctor connectivity`
instead of becoming a root browser command or compatibility shim.

Doctor output is normalized through `_emit`; manual JSON serialization and
text-only subcommands are removed from the redesigned surface.

Quarantine becomes bucket-scoped before it is treated as final
storage-maintenance behavior.

`setup_reset` does not remain the owner of quarantine behavior if that keeps
storage maintenance outside `config doctor`.

Direct secure-object load failures still need command-level handling so
user-facing failures can point to `aeat config doctor` instead of surfacing raw
decrypt errors.

The following command shapes are rejected:

- Root `aeat browser`
- Root `aeat doctor`
- `aeat config doctor-logs`
- `aeat app doctor`
- `aeat app config doctor connectivity`
- `aeat app bucket`
- `aeat app quarantine`
- Other app-scoped storage-maintenance routes
- Compatibility aliases or shims for browser health
- Legacy `--json` on redesigned doctor commands
- `doctor repair`

## 2026-05-14 amendment — test-user audit finding P1 #5 (doctor retirement)

This ADR is retired, not patched. The earlier draft of this amendment
proposed promoting a `next:`/`report:` rule into the doctor surface; that
draft is withdrawn. The `aeat config doctor` namespace and every one of
its historical subcommands (`connectivity`, `integrity`, `list`,
`quarantine`, `logs`) are removed from the redesigned CLI. The
exhaustiveness rule lives natively on `aeat config repair`'s
`DiagnosticCheck` discriminated union; see the config-repair-shape ADR's
"absorbs from retired `config doctor`" section for the unambiguous rule
statement and the per-failure-class mapping.

W70.P334 carries out the removal in source: it deletes the
`aeat config doctor` Typer entrypoint, removes its Typer wiring, removes
the legacy diagnostic emitters that do not ship `next:`/`report:` fields,
and removes every help reference, refusal-message reference, and
i18n-translated reference to `aeat config doctor`. There is no shim,
no alias, no compatibility flag. The doctor surface does not co-exist
with the repair surface during a transition window: it is removed in
the same wave that proves repair-surface exhaustiveness.

Acceptance criteria (delegated to the repair-shape ADR and to W70.P334):

- `aeat config doctor` is unregistered; `aeat config doctor --help` exits
  with the standard unknown-command exit code.
- Every `aeat config repair` diagnostic class (quarantinable rows,
  `secure_state.load` schema-shape mismatch, master-key handling failure,
  unknown integrity-warning class) ships either `next:` or `report:`.
- `aeat config repair` produces ZERO false-positive diagnostics on a
  freshly-initialised default profile.
