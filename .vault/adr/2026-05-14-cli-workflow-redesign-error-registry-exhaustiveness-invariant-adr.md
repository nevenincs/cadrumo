---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `error registry exhaustiveness invariant` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`.

## Problem Statement

`aeat app overview status` crashes with:

```text
ValueError: AeatError subclass aeat.application.modelo._actions.AmendmentVerificationRefusedError is missing a declared ErrorCode registry entry
```

The same defect class was previously addressed for `RegistryApplicationError`
by adding a declared `ErrorCode` entry. The fix was class-scoped. Other
`AeatError` subclasses can ship without a registry entry and remain
quiet until their import path is triggered by a specific command. The
failure is therefore non-deterministic with respect to ordinary user
journeys.

## Considerations

`ERROR_REGISTRY` is the central authority for translating internal
exceptions into operator-facing error envelopes. Any `AeatError` subclass
without an entry cannot be routed through `command_error_boundary`,
`render_error_text`, or `render_error_json`. The defect is structural
rather than localized: every subclass added in the future without an
entry will reproduce the crash for whichever command first imports it.

The redesigned CLI declares the central error facilities as boundary
contract (apex ADR, CLI Backend Boundary section). Drift in the registry
silently violates that contract.

## Constraints

- The fix MUST be a repo-wide invariant, not a class-by-class patch.
- The invariant MUST fail at import time or in CI, not at the moment a
  user runs the command that imports the offending subclass.
- No compatibility shim that ships a fallback `ErrorCode` for unregistered
  subclasses is acceptable; silent fallback masks the defect rather than
  fixing it.

## Implementation

The package declares two enforcement points; both MUST exist.

1. **Import-time invariant.** The package's top-level import (the
   canonical `aeat` package's `__init__` or its central errors module
   load path; the implementation step picks the exact site) walks every
   subclass of `AeatError` reachable from imported submodules and asserts
   each has a declared `ErrorCode` entry in `ERROR_REGISTRY`. A missing
   entry raises `RuntimeError` synchronously. Production startup fails
   loudly; the failure does not depend on which user command triggered
   the import path.

2. **CI test.** A repo-wide test (placed alongside the central errors
   module) imports every package submodule (via a deterministic
   `pkgutil.walk_packages` traversal anchored at the `aeat` package
   root), then collects every `AeatError` subclass and asserts each has
   a registry entry. The test runs on every PR and rejects merges that
   add an unregistered subclass.

Both enforcement points consult the same source of truth (`ERROR_REGISTRY`
plus the live class hierarchy). Neither relies on a hand-maintained
allow-list.

The `ErrorCode` entry for `AmendmentVerificationRefusedError` is added as
part of this ADR's implementation step. Any other subclass currently
missing an entry is added in the same step; the import-time invariant
keeps it honest going forward.

## Rationale

The defect class is "registry drift": a structural invariant ("every
`AeatError` subclass declares an `ErrorCode`") is enforced only by code
review and reactive patches when users hit the crash. Promoting the
invariant into import-time and CI-time enforcement makes drift
unreachable. This matches the project's broader stance: contracts that
matter live in the type system or in CI, not in convention.

## Consequences

- The import-time check adds a small startup cost (one traversal of
  loaded modules). The cost is paid once per process and is bounded by
  the subclass count.
- Adding a new `AeatError` subclass requires adding the corresponding
  `ErrorCode` entry in the same PR. The CI test refuses merges
  otherwise.
- The crash trail surfaced by the audit on `aeat app overview status` is
  closed; the same defect cannot reappear silently for any other command.
- No backward-compat path is preserved. There is no "warn-on-missing"
  mode and no opt-out flag.
