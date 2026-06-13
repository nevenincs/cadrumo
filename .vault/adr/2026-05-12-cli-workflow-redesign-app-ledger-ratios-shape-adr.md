---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
---



# `cli-workflow-redesign` adr: `app ledger ratios shape` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

Usage ratios belong under the application ledger workflow. Apex §4.2 places
`usage_ratios` under `app ledger ratios`, while the retired financial root still
contains stale, unmounted ratio commands.

The old grammar is asymmetric: `ratios list`, `set-ratio`, and `unset-ratio`.
It also lives under the retired `financial profile` surface. The redesign needs
a bucket-scoped ledger command family that does not conflate proportional
deduction with IVA prorrata.

## Considerations

The ledger transaction model requires bucket-scoped, evented mutations.
Mixed-use rows need proportionality context, and the existing `usage_ratios`
domain already persists category-keyed encrypted profile data under namespace
`aeat.domain.usage_ratios`, key `profile`, version `1`.

Usage ratios are not IVA prorrata. They represent proportional deduction or a
business/personal split coefficient. Prorrata remains a future Modelo 303/390
concern; Modelo 130 needs proportional deduction through ledger-to-renta.

## Constraints

- No compatibility aliases or shims are allowed.
- The retired `financial profile` public CLI is removed.
- Ratio mutations are bucket-scoped and evented.
- `KEY` resolves to a concrete `SpendingCategory.value` or CLI-only family
  alias; alias names are never persisted.
- User-facing language uses "usage ratios", "proportional deduction", or
  "business/personal split coefficient".
- `prorrata` wording is reserved for future IVA prorrata functionality.

## Implementation

Adopt `aeat app ledger ratios` as the public CLI grammar:

```text
aeat app ledger ratios list [--format json|text]
aeat app ledger ratios set KEY VALUE [--format json|text]
aeat app ledger ratios unset KEY [--format json|text]
```

Optional future read helpers:

```text
aeat app ledger ratios show KEY [--format json|text]
aeat app ledger ratios eligible [--format json|text]
```

Use `ratios` as a noun group and normalize verbs to `list`, `set`, and
`unset`.

Reject public grammars:

- `aeat financial profile`
- `aeat app ledger profile ratios`
- `aeat app ledger set-ratio`
- `aeat app ledger ratios set-ratio`
- `aeat app modelo ratios`
- `aeat app ledger prorrata`

Mutation events:

- `ledger.ratios.set`
- `ledger.ratios.unset`

Event payload includes schema version, bucket id, actor/source command, raw
key, resolved category ids, previous ratio, new ratio for `set`, outcome,
timestamp, and target object ref `aeat.domain.usage_ratios/profile`.

`list` text output includes category, kind, user ratio, default, and source.
`list` JSON output includes `bucket_id` and `ratios`.

`set` JSON output includes `bucket_id`, operation `ledger.ratios.set`, key,
ratio, updated categories, and `event_id`.

`unset` is idempotent when no persisted value exists and reports whether state
changed.

## Rationale

The ratios surface is ledger configuration for transaction proportionality,
not profile management and not modelo calculation. It belongs before the
ledger-to-modelo handoff because modelo calculations consume resolved ledger
facts.

Keeping the noun group `ratios` and verbs `list`, `set`, and `unset` matches
the redesigned command grammar and removes legacy asymmetry. Explicitly
reserving `prorrata` avoids hiding a separate IVA legal mechanism inside a
proportional deduction helper.

## Consequences

The public ratio workflow moves to the application ledger surface and aligns
with bucket-scoped ledger behavior.

The old financial profile public CLI is removed without compatibility aliases.
Any required migration is backend/internal only.

Tests prove that retired commands are absent, the new commands work, aliases
resolve without persisting alias keys, bounds remain `[0,1]`, and set/unset
operations emit the required ledger ratio events.

## 2026-05-15 amendment - event emission lock

The 2026-05-15 ground-truth audit found that `set_usage_ratios` /
`unset_usage_ratios` paths persist correctly but **emit no bucket
events**. The `ratios_set` and `ratios_unset` CLI handlers call
`save_usage_ratios` directly without invoking
`append_bucket_event`. This amendment locks the emission contract so
the gap is closed in a follow-up wave.

Required `BucketEventType` additions: `LEDGER_RATIOS_SET`,
`LEDGER_RATIOS_UNSET`. Both events MUST carry the `usage_ratio_id`,
`category`, prior value (or `null` for a first set), and new value
(or `null` for unset) in the payload.

Required service surface: every code path that mutates a usage ratio
MUST go through a single application-layer entry point that appends
the matching event after persistence. CLI handlers MUST NOT skip the
service call. A boundary regression test asserts no shadow path can
write to `usage_ratios` storage without emitting.

The `eligible` and `validate` verbs from the 2026-05-13 extension
remain read-only and do not emit events.

## 2026-06-03 amendment — composition-pattern alignment

The W77.P370.S2131 BucketMaintenanceService landing established the
composition pattern locked by `[[2026-06-03-cli-workflow-redesign-adr]]`:
new application-layer services delegate cross-store writes to
existing single-writer primitives and consume those primitives
through the top-level package `__all__` re-export, never through
internal submodule imports. The ratios service surface MUST align
with this discipline at the next maintenance edit:

- The `ratios_set` / `ratios_unset` paths route their writes
  through a single application-layer entry point that delegates to
  the existing `save_usage_ratios` domain primitive and emits the
  matching `LEDGER_RATIOS_SET` / `LEDGER_RATIOS_UNSET` event in
  the same call. This is the per-domain analogue of the
  bucket-maintenance two-event co-emission (a domain mutation event
  alongside the surface-invocation event); for ratios there is no
  separate "lifecycle" event so the surface event is the sole
  emission.

- The `eligible` and `validate` read-only verbs consume
  `load_usage_ratios`, `effective_usage_ratio`, and
  `resolve_category_profiles` through the
  `aeat.domain.usage_ratios` / `aeat.domain.categories` package
  boundaries (already top-level `__all__` re-exports).
  `_ratios.py:list_eligible_ratios_for_bucket` already follows this
  shape.

Codified by:
- `composition-service-no-parallel-write-path` — the ratios
  service MUST NOT re-implement `save_usage_ratios`; it
  delegates and emits.
- `service-imports-via-top-level-reexports` — every domain
  primitive is consumed through the package `__all__`, never
  via a `from aeat.domain.usage_ratios._foo import bar` dot-in.
