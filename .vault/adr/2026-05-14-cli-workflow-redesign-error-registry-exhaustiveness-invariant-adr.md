---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-07-17'
related:
  - "[[2026-04-25-error-code-registry-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-observability-wrapping-decision-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
  - "[[2026-07-12-cadrumo-cli-executable-adr]]"
---

# `cli-workflow-redesign` adr: `error registry exhaustiveness invariant` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement
business logic, schema conversion logic, validation policy, orchestration rules,
persistence behavior, provider behavior, or compatibility/deprecation shims.
CLI commands MUST delegate to centralized, tested backend, application, and
domain services.

CLI logging and error handling MUST use the central facilities:
`cadrumo.core.logging.get_logger(__name__)`,
`cadrumo.core.logging.SecretScrubbingFilter`, and the public
`cadrumo.core.errors` facade: `CadrumoError`, `ERROR_REGISTRY`, `ErrorCode`,
`ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`,
`render_error_json`, `get_error_exit_code`, and
`get_registered_error_code`. CLI command execution MUST pass through
`cadrumo.entrypoints.cli._errors.command_error_boundary`, with app decoration
through `decorate_typer_app`; `CliValidationBoundaryError`,
`CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr`
remain boundary adapters only.

CLI output MUST use the established emitters, including
`cadrumo.entrypoints.cli._common._emit` and the shared
`cadrumo.core.json_contract.emit_json_success` /
`cadrumo.core.json_contract.emit_json_document` functions.

## Problem Statement

`aeat app overview status` crashes with:

```text
ValueError: CadrumoError subclass cadrumo.application.modelo._action_errors.AmendmentVerificationRefusedError is missing a declared ErrorCode registry entry
```

The original defect was class-scoped: adding the missing row corrected one
exception but did not prove that every other production `CadrumoError` had exactly
one code. Without structural enforcement, a gap remains quiet until the
defining module is imported or the exception reaches the rendering boundary.

## Considerations

`ERROR_REGISTRY` is the central authority for translating internal
exceptions into operator-facing error envelopes. Any `CadrumoError` subclass
without an entry cannot be routed through `command_error_boundary`,
`render_error_text`, or `render_error_json`. The defect is structural
rather than localized: every subclass added in the future without an
entry will reproduce the crash for whichever command first imports it.

The redesigned CLI declares the central error facilities as boundary
contract (apex ADR, CLI Backend Boundary section). Drift in the registry
silently violates that contract.

## Constraints

- The fix MUST be a repo-wide invariant, not a class-by-class patch.
- Normal class declaration MUST fail immediately when the catalogue is loaded
  and the declared class has no registry row.
- The circular-import initialization window MAY defer binding, but the deferred
  queue MUST resolve against the same catalogue on the first registry lookup;
  it MUST NOT create a fallback or an alternate authority.
- CI MUST deterministically import-walk the complete production `cadrumo.*`
  package, prove every concrete `CadrumoError` has one registered code, and prove
  every code has one class owner.
- No compatibility shim that ships a fallback `ErrorCode` for unregistered
  subclasses is acceptable; silent fallback masks the defect rather than
  fixing it.

## Implementation

The package declares three complementary enforcement points; all MUST exist.

1. **Class-declaration binding.** `CadrumoError.__init_subclass__` calls
   `cadrumo.core.errors.bind_error_code`. Once the explicit qualified-class
   catalogue is loaded, declaring an unregistered subclass raises `ValueError`
   while its defining module is imported. Production does not perform a
   top-level walk of every package module, and lightweight surfaces such as
   bare `aeat --version` are not required to pay that cost.

2. **Circular-initialization completion.** If a subclass is declared while
   `cadrumo.core.errors._registry` is still constructing the catalogue,
   `bind_error_code` places only the class in a deferred queue.
   `get_registered_error_code` drains that queue and resolves it exclusively
   against the completed explicit catalogue. A missing row still raises
   `ValueError`; no generic code, warning mode, alias table, or silent fallback
   is permitted.

3. **CI exhaustiveness test.** The unit suite beside the central errors module
   uses deterministic `pkgutil.walk_packages` traversal rooted at `cadrumo`,
   imports every production package submodule, collects every concrete
   `CadrumoError` subclass, and verifies:
   - every subclass binds to a declared code;
   - every code maps to exactly one subclass;
   - no qualified class or code is declared twice;
   - every category is represented; and
   - production raise sites neither instantiate bare `CadrumoError` nor reference
     an unresolved registered subclass.

All three enforcement points consult the same explicit catalogue and public
`ERROR_REGISTRY` projection. The `ErrorCode` entry for
`AmendmentVerificationRefusedError`, and any future production subclass, must
land in that catalogue in the same change as the class.

## Rationale

The defect class is registry drift: a structural invariant ("every concrete
`CadrumoError` has exactly one `ErrorCode`") cannot depend on code review and
reactive patches. Declaration-time binding catches ordinary imports early,
the narrowly scoped deferred queue handles only the registry's own
initialization cycle, and the deterministic CI walk supplies complete-package
proof. This keeps the invariant strong without imposing an inaccurate
production startup traversal.

## Consequences

- Normal module imports fail at the class declaration that introduces a missing
  code once the catalogue is ready.
- The registry's circular initialization may postpone the binding check until
  first registry resolution, but it cannot manufacture a code or admit an
  undeclared class.
- Full-package traversal is a CI responsibility, not a production startup cost.
- Adding a new `CadrumoError` subclass requires adding the corresponding
  `ErrorCode` entry in the same PR. The CI test refuses merges
  otherwise.
- The crash trail surfaced by the audit on `aeat app overview status` is
  closed; the same defect cannot reappear silently for any other command.
- No `aeat` Python package, backward-compatibility path, warn-on-missing mode,
  fallback code, or opt-out flag is preserved.
