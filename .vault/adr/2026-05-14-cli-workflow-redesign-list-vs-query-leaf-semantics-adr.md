---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-live-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-root-help-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `list-vs-query leaf semantics` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`.

## Problem Statement

Several leaves named `list` require selectors before they will run:

- `aeat app modelo bindings list` requires `--modelo`, `--year`, `--period`.
- `aeat app live filed list` requires `--modelo`.
- `aeat app ledger export` requires `--output`.

A leaf that refuses to run without selectors is a query, not a list.
Operators reach for `list` as the unconditional "show me what is in
here" verb. Forcing them to discover selector shape first (often by
running a different command to learn what `--modelo` accepts) breaks
the discovery loop the help surface promises.

## Considerations

The redesigned CLI is built around a workflow-ordered help shape and a
two-root invariant. Operators navigate by reading help text. The verb
name in help text is the operator's promise about the verb's behavior.
Cross-leaf inconsistency in what `list` means destroys that promise.

`export` is a different case: its mandatory `--output` argument is the
verb's reason for existing. Renaming `export` to `list` is not on the
table; the fix there is to surface a default destination or, where the
operator's intent is "show me what would be exported", a separate
`list`-shaped read verb.

## Constraints

- The root contract remains exactly `aeat config` and `aeat app`.
- No verb renamings that introduce a third CLI root.
- No compatibility shim that keeps mandatory-selector `list` behavior
  available behind a flag.
- `list` is reserved for the unconditional-default reading shape.

## Implementation

The semantic contract for `list`:

- A leaf named `list` MUST default to the unfiltered set of records the
  surface owns, scoped to the active profile/bucket.
- Every selector (`--modelo`, `--year`, `--period`, `--status`,
  `--missing`, and so on) MUST be optional and act as a refining filter.
- Selectors that accept a closed-domain value (modelo code, period
  code) MUST validate against a registry-derived or domain-derived
  enum. The accepted set is surfaced through `--help` (Typer choice or
  inline help text).
- A leaf that genuinely needs mandatory selectors is not a `list`. It
  is renamed to a domain-appropriate verb (`show`, `find`, `match`,
  etc.) so the help surface tells the truth about its semantics.

The semantic contract for `export`:

- `export` retains its mandatory output argument; that is the verb's
  point.
- Where operators need a "what would be exported" preview, a sibling
  `list` or `preview` leaf is added with the unconditional-default
  shape above. The implementation step decides per-surface whether the
  preview is necessary.

Per-leaf application of this ADR:

- `aeat app modelo bindings list`: selectors become optional; see
  `app-modelo-bindings-shape` amendment.
- `aeat app live filed list`: selectors become optional; see
  `app-live-shape` amendment.
- `aeat app ledger export`: stays mandatory-output; if a "show me what
  would be exported" surface is desired, the implementation step adds a
  sibling read leaf rather than relaxing `export`.

A test traverses the Typer app graph at boot and asserts that every leaf
named `list` accepts an invocation with no required arguments beyond the
root-level `--format` and `--profile`-equivalent options. The test fails
if any `list` leaf raises a Typer `MissingParameter` on bare invocation.

## Rationale

`list` is the discovery verb. Forcing operators to discover selector
shape before they can list anything inverts the promise. Promoting the
unconditional-default semantics into a graph-level test makes the
promise unfalsifiable; the contract cannot drift back without the test
failing.

`export` is a producer verb, not a discovery verb. Its mandatory output
is correct; the audit's complaint is that an `export` with mandatory
`--output` is not a discovery surface, and conflating it with `list`
would be the wrong fix.

## Consequences

- Per-leaf amendments in this ADR's related shape ADRs implement the
  optional-selector shape.
- The Typer graph test joins the CLI surface test suite.
- Help text and translations for affected leaves are updated to reflect
  the new optional-selector shape.
- No backward-compat path is preserved.
