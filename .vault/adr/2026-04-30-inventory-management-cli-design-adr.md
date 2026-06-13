---
tags:
  - "#adr"
  - "#inventory-management"
date: 2026-04-30
modified: '2026-04-30'
related:
  - "[[2026-04-30-inventory-management-cli-design-research]]"
  - "[[2026-04-29-inventory-management-adr]]"
  - "[[2026-04-30-inventory-management-cli-design-reference]]"
---

# inventory-management cli design adr: canonical data ledgers ux

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Status

Accepted.

## Problem statement

The inventory and amortization feature currently exposes `aeat profile assets` and `aeat profile inventory`. That surface is prototype-compatible only. It does not match the Kent-first CLI language, it suggests profile configuration rather than financial evidence preparation, and it sits on plaintext Path A JSON persistence that is not acceptable for production financial ledgers.

The feature needs a corrected canonical UX before hardening continues. Otherwise persistence, valuation, output contracts, tests, and documentation will lock onto the wrong command tree.

## Decision

Replace the future canonical inventory and amortization UX with `aeat data ledgers ...`.

After implementation, the canonical hardened command family is rooted under `aeat data ledgers`. Inventory and amortization ledgers are financial evidence preparation work, so they belong under the Kent-first `data` domain.

Current `aeat profile assets` and `aeat profile inventory` commands remain temporary prototype-compatible commands until the canonical surface exists. After `aeat data ledgers ...` is implemented and tested, the public profile ledger commands should be removed rather than kept as forwarding commands. They must not be documented as the future canonical UX.

Future syntax examples:

```text
aeat data ledgers assets add ...
aeat data ledgers assets show ...
aeat data ledgers assets amortization preview ...
aeat data ledgers assets amortization apply ...
aeat data ledgers inventory create ...
aeat data ledgers inventory movement add ...
aeat data ledgers inventory valuation preview ...
aeat data ledgers inventory valuation apply ...
aeat data ledgers anexo-d preview --modelo 100 --year 2025
aeat data ledgers anexo-d apply --modelo 100 --year 2025
```

These examples are future syntax. They must not be represented as current shipped commands until implemented.

## Scope

The rewrite covers command tree shape, persistence, VAT/base decomposition, amortization calculation, inventory valuation, output contracts, error handling, i18n, migration, scenario tests, and documentation.

Casilla `0155` remains inventory or stock variation. Casilla `0173` remains fixed-asset amortization. The implementation and documentation must preserve that mapping.

## Constraints

Ledger commands remain local-only. They must not imply live AEAT submission or live AEAT mutation.

Mutating commands must use preview/apply semantics where calculation, migration, overwrite, or Anexo D overlay effects need user review.

The CLI must not silently overwrite duplicate asset IDs, ledger IDs, movement IDs, or migration targets.

Financial ledger storage must target the #216 governed encrypted persistence substrate with `SensitivityClass.FINANCIAL`, not plaintext Path A JSON under `~/.config/aeat`.

Existing plaintext stores must be detected and migrated through an auditable migration path.

JSON support is not assumed. A command supports JSON only after it is registered in the shared schema catalogue and tested against the shared JSON envelope.

Errors must use registered error codes and stable categories. LIFO refusal, duplicate IDs, invalid dates, invalid decimals, invalid asset classes, missing ledgers, missing assets, negative stock, plaintext detection, and unsupported JSON must be registered or mapped to registered errors before the commands are considered hardened.

Human output must be ASCII-safe and prepared for trilingual messages. Profile banners are a future requirement and command output should leave room for active profile and actividad context.

## Rationale

`data` is the Kent-facing domain for financial evidence preparation. Ledgers are not identity profile setup; they are structured financial evidence used to derive filing inputs. Placing them under `aeat data ledgers` aligns the feature with the CLI wireframe language and avoids overloading `profile`.

Keeping current profile commands temporarily reduces migration risk while the canonical surface does not exist. Removing them after the canonical surface lands keeps the CLI lean and avoids duplicate command paths for the same ledger task.

A full rewrite is justified because the audit findings are structural. Plaintext persistence, missing VAT/base decomposition, raw libertad behavior, useful-life cap bypass, future-entry cumulative leakage, false FIFO/PMP labeling, bounded JSON support, and silent overwrite behavior cannot be solved by help text alone.

## Consequences

Implementation plans should target `aeat data ledgers ...` as the canonical command tree.

The existing inventory ADR remains historically valid for the v1 prototype boundary, but this ADR supersedes it for future canonical UX and production hardening.

Current profile commands may be preserved during transition but must be labeled as current prototype-compatible commands, not as the destination UX.

Documentation must avoid claiming that future syntax is available until the command tree exists and tests prove it.

The storage migration becomes mandatory for production readiness. Plaintext Path A JSON can be an input to migration, but not the accepted target storage.

The valuation engine must implement real FIFO and PMP layer behavior before those labels are presented as calculation semantics.

The JSON and error contracts become acceptance gates for any command advertised to automation users.

## Rejected alternatives

Keep `aeat profile assets` and `aeat profile inventory` as canonical.

This keeps the implementation closer to current v1 but preserves the wrong mental model. Financial ledgers are not profile setup, and the profile namespace is already overloaded.

Move directly to `aeat assets` and `aeat inventory`.

This makes the commands shorter but breaks the Kent-first root taxonomy. It adds more top-level nouns instead of grouping evidence preparation under `data`.

Document profile commands as current and future.

This would be inaccurate. The current commands are prototype-compatible only and do not satisfy the hardened persistence, valuation, output, and error contracts.

Keep old profile commands public after replacement.

This would keep scripts working but would make the CLI heavier and less clear. The lean target has one public path for ledger work.

## Acceptance criteria

`aeat data ledgers ...` exists as the canonical command tree for hardened inventory and amortization workflows.

Current profile commands are removed from the public Kent-facing CLI after canonical commands exist.

Financial ledgers persist through governed encrypted `SensitivityClass.FINANCIAL` storage with plaintext detection and migration.

VAT/base decomposition is explicit and audited.

Casilla `0155` and `0173` mappings are preserved and tested.

FIFO and PMP labels correspond to true valuation-layer behavior.

All advertised JSON commands are registered and tested against the shared JSON envelope.

All user-facing failures use registered error codes and stable categories.

Scenario tests cover VAT rates `0`, `4`, `10`, and `21`, multi-year purchases, shared assets, multiple actividades, returns, corrections, invalid input, LIFO refusal, negative stock, duplicate IDs, plaintext detection, and JSON automation.
