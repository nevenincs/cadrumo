---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
---



# `cli-workflow-redesign` adr: `config repair shape` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`.

## Problem Statement

The redesigned CLI root is constrained to exactly:

```text
aeat config
aeat app
```

Configuration health and storage maintenance need one stable home under
`aeat config`. The namespace MUST:

- Speak plain English to first-time operators. Operators reach for words like
  "repair" or "fix", not "doctor"; the namespace name is the first signal a
  blocked user sees and must be self-evidently actionable.
- Always close the loop. Every fail or warn row a diagnostic emits MUST point
  at a concrete next command, or explicitly state that no further automated
  action is available. Silent dead-ends leave the operator guessing.
- Cover the real recovery surface. Secure-object quarantine is only one of
  the persisted maintenance actions the backend can support. WorkflowState
  schema drift (frozen Pydantic model rejecting an older envelope's
  bucket_events list or string updated_at) leaves an otherwise functional
  install wedged with no automated route to a clean slate.

## Considerations

Backend diagnostics surface runtime readiness, registry loading, workflow
state, setup/profile/auth readiness, and AES-256-GCM secure-object
readability. Browser health and future adapter probes belong with the same
namespace. The bare invocation runs the composite report; subcommands
narrow scope.

The persisted-mutation surface is grouped under the same root because the
operator's mental model is unified: "something is wrong, run the thing that
fixes it." Splitting diagnose from repair across two roots forces operators
to remember which side a given symptom lives on. A single root command with
read-only subcommands by default and explicit `--yes` gating on the
mutating subcommands preserves safety without fragmenting the namespace.

WorkflowState envelopes are persisted as a single encrypted secure-object
row under namespace `aeat.workflow`, key `state`. When the envelope fails
Pydantic validation, the existing inline-profile migration path covers one
specific legacy shape; other drift (frozen-model field types changing across
versions, e.g. tuple-vs-list, datetime-vs-string) raises `WorkflowError`
with a textual suggestion that never reaches the operator because the
diagnostic row carries no `next_action`. The right fix is two-part: every
fail row gets a `next_action`, and a real `reset-state` subcommand exists
so the suggestion has somewhere to point.

## Constraints

- Root command shape remains exactly `aeat config` and `aeat app`.
- Storage and configuration diagnostics and maintenance belong under
  `aeat config`.
- No app-scoped bucket, quarantine, reset-state, or storage-maintenance
  commands are introduced.
- Every redesigned command renders through `_emit` and supports
  `--format json|text`.
- Every persisted mutation is bucket-scoped and emits a bucket event.
- Every persisted mutation requires explicit `--yes`.
- Every diagnostic row whose status is `fail` or `warn` carries either a
  populated `next_action` field or an explicit `dead_end` reason. A row
  may not be silent. This is a type-system contract, not a convention.
- Compatibility aliases, deprecation shims, and legacy `--json` are not
  allowed.

## Implementation

`aeat config repair` owns configuration health, storage integrity, and
storage maintenance for the redesigned CLI. The accepted grammar is:

```text
aeat config repair [--format json|text]

aeat config repair connectivity
    [--target browser|auth|sede|all]
    [--format json|text]

aeat config repair integrity
    [--namespace NAMESPACE]
    [--format json|text]

aeat config repair list <namespace>
    [--all|--unreadable]
    [--format json|text]

aeat config repair quarantine
    [--namespace NAMESPACE]
    [--dry-run]
    --yes
    [--format json|text]

aeat config repair reset-state
    [--dry-run]
    --yes
    [--format json|text]

aeat config repair logs
    [--lines N]
    [--format json|text]
```

The bare `aeat config repair` invocation (no subcommand) runs the
composite health report: `connectivity`, `integrity`, registry load,
secure-state load, profile and auth readiness, and recent log surface. It
is the canonical "is everything OK?" entry point. Subcommands run the
same checks with finer control.

`connectivity` absorbs browser health and future adapter probes.
`integrity` owns secure-object AES-256-GCM tag verification scans.
`list` provides secure-object inventory and drill-down.
`logs` emits the recent log tail through `_emit`.

`quarantine` and `reset-state` are the persisted mutations. Both require
`--yes`. Both emit bucket events in the same logical transaction as the
mutation. Read-only diagnostics emit no bucket events.

Required events:

```text
secure_object.quarantined
workflow_state.reset
```

The `workflow_state.reset` event payload includes a fingerprint of the
discarded envelope (schema_version, written_at, byte length, the reason
class that triggered the reset), the bucket id of the active profile if
recoverable, and the actor/source/timestamp. The discarded envelope is
not retained in plaintext.

Future events are allowed only when their backends exist:

```text
secure_object.restored_from_quarantine
secure_object.repaired
```

### Always-actionable diagnostic rows

`DiagnosticCheck` becomes a discriminated union at the Pydantic layer:

- `status == "ok"` → no `next_action`, no `dead_end`.
- `status == "fail"` or `status == "warn"` → exactly one of `next_action`
  (a runnable `aeat …` command string) or `dead_end` (a short explanation
  of why no automated route exists) MUST be populated. A row that supplies
  neither, or both, is a `ValidationError` at construction time.

The text renderer prints `next: <command>` for `next_action` rows and
`note: <reason>` for `dead_end` rows. The JSON renderer surfaces both
fields explicitly.

The mapping for the rows the existing implementation already produces:

| row name | failure mode | next_action |
| --- | --- | --- |
| `environment.python` | unsupported Python | `dead_end: upgrade Python` |
| `package.version` | n/a (always ok) | — |
| `logging.file` | log dir missing | `aeat config repair logs` |
| `registry.load` | load failure | `dead_end: registry is bundled; reinstall aeat` |
| `secure_state.load` | envelope unreadable | `aeat config repair reset-state --yes` |
| `secure_objects.integrity` | unreadable rows present | `aeat config repair quarantine --yes` |
| `profile.readiness` | missing required keys | `aeat config init --tax-id … --activity …` |
| `auth.readiness` | provider unconfigured | `aeat config auth setup` |

The `next_action` field carries the exact command string the operator
should run. Renderers MUST NOT paraphrase or shorten it.

### `reset-state` semantics

`reset-state` is the recovery route for an unreadable WorkflowState
envelope. It deletes the single secure-object row at namespace
`aeat.workflow`, key `state`, and emits the `workflow_state.reset` event
against the active bucket if one is recoverable, or against a system
bucket otherwise. It does NOT touch profile buckets, ledger rows, modelo
filing records, run records, or any other namespace. After reset the
next read of WorkflowState returns a fresh empty `WorkflowState()`, which
is the same state a never-initialized install begins from.

`--dry-run` reports the envelope fingerprint that would be discarded and
does not mutate. `--yes` is mandatory for the mutating run; the command
exits with the validation-refusal exit code if `--yes` is absent.

## Rationale

The namespace name was chosen by the operator vocabulary, not the
maintenance taxonomy. Operators arriving at a wedged install reach for
"repair" or "fix"; "doctor" reads as jargon and stops users from
discovering the command at all. "Repair" reads as both diagnose ("show
me what is wrong") and act ("fix it"), matching the bare-invocation /
subcommand split.

Keeping diagnose and mutate under the same root preserves the two-root
contract and matches the operator's mental model. The `--yes` gate keeps
safety without splitting the namespace.

The always-actionable row contract eliminates the failure mode the
testimonial surfaced: a diagnostic that knows what is wrong but walks
away without telling the operator how to act. Promoting the contract
into the Pydantic model makes the failure mode unreachable by
construction.

`reset-state` closes the gap that `quarantine` cannot cover.
`quarantine` is scoped to the secure-objects integrity table and cannot
heal an unreadable WorkflowState envelope. Adding a focused single-row
reset is the smallest surface that unwedges the testimonial flow while
preserving every other bucket of operator data.

## Consequences

The composite report under `aeat config repair` replaces the historical
diagnostics namespace. The redesigned CLI has no `aeat config doctor`,
`aeat doctor`, `aeat repair`, `aeat app repair`, or any compatibility
alias. The historical browser health command remains absorbed into
`aeat config repair connectivity`.

Doctor-output normalization moves under the new namespace; the `_emit`
contract is unchanged.

The `DiagnosticCheck` model becomes a discriminated union. Constructing
a fail or warn row without either `next_action` or `dead_end` raises
`ValidationError`. Existing call sites that produce a silent failing
row MUST be updated to supply the appropriate field; this is a
type-system enforcement, not a convention.

The `WorkflowError` raised by `workflow_state_repository().load` no
longer needs to embed a recovery suggestion in its message; the
diagnostic row's `next_action` is now the single source of operator
recovery guidance.

`workflow_state.reset` joins the bucket event taxonomy. The event
payload schema is locked to envelope fingerprint plus actor metadata;
no plaintext envelope content is recorded.

The following command shapes are rejected:

- `aeat config doctor` and any of its historical subcommands
- Root `aeat doctor`
- Root `aeat repair`
- Root `aeat browser`
- `aeat app repair`
- `aeat app doctor`
- `aeat app bucket`
- `aeat app quarantine`
- `aeat config reset --scope profile --yes` as the recovery route for
  workflow-state shape drift (the route is `aeat config repair
  reset-state --yes`)
- Compatibility aliases, deprecation shims, or legacy `--json`
- `aeat config repair repair` and any nested duplicate-verb subcommand

## Absorbs from retired `config doctor`

The `aeat config doctor` namespace is retired by this ADR. The
`next:`-or-report exhaustiveness rule that earlier drafts proposed for
the doctor surface lives natively here, as a typed contract on
`DiagnosticCheck`. The rule is restated unambiguously below so no
reader has to chase the retired ADR for the canonical statement.

### Exhaustiveness rule (restated, native to `config repair`)

Every diagnostic row whose `status` is `fail` or `warn` MUST carry
exactly one of the following two fields, populated at construction
time:

- `next_action: <verbatim aeat command>` — a single concrete runnable
  leaf invocation the operator can copy-paste to make progress. The
  command MUST resolve to a registered Typer leaf, not a group.
- `dead_end: <verbatim guidance>` (rendered as `report:` in
  `--format text`) — a non-recoverable finding the operator cannot
  self-fix. The guidance MUST tell the operator what to capture and
  where to report it.

The `DiagnosticCheck` Pydantic model REFUSES at construction time to
build a `fail`/`warn` row that has neither field, or that has both. This
is a type-system contract, not a convention. There is no opt-in flag,
no per-emitter exemption, no half-and-half.

### Failure classes covered (no row may be silent)

Every failure class the diagnostic surface can emit MUST ship either a
`next_action` or a `dead_end`. The four classes called out by the
2026-05-14 audit are bound below; the same rule extends to every other
class enumerated in the implementation table above.

| failure class | shipped field | value |
| --- | --- | --- |
| quarantinable rows present in secure-objects integrity scan | `next_action` | `aeat config repair quarantine --yes` |
| `secure_state.load` schema-shape mismatch (envelope unreadable under the current frozen Pydantic model) | `next_action` | `aeat config repair reset-state --yes` |
| master-key handling failure (derivation refuses, key material unreadable, or KEK rotation incomplete) | `dead_end` | `report: master-key state is incompatible with this build; capture the `aeat config repair logs` tail and file an issue` |
| unknown integrity-warning class (a finding the emitter cannot map to a known class) | `dead_end` | `report: this finding is not classifiable by the current emitter; capture full `aeat config repair --format json` output and file an issue` |

No half-and-half. Every class above ships exactly one of `next_action`
or `dead_end`. A class that ships neither is a regression.

### No false positives on a freshly-initialised profile

`aeat config repair` MUST produce ZERO `fail` and ZERO `warn` rows when
invoked against a freshly-initialised default profile (the state
immediately after `aeat config init` succeeds, with no further operator
action). A finding that fires on a clean profile is a regression to be
removed or suppressed AT SOURCE — not annotated as "expected noise",
not gated behind a flag, not allow-listed. This mirrors the
no-false-positive rule on `aeat app review queue` (apex audit finding
#9, app-review-queue-execution ADR); the two surfaces share the same
operator-trust contract.

This is a non-negotiable acceptance criterion for the W70.P334 phase.
A CLI smoke test runs `aeat config init` on a clean profile and asserts
the immediately-following `aeat config repair --format json` payload
carries zero `fail` and zero `warn` rows.
