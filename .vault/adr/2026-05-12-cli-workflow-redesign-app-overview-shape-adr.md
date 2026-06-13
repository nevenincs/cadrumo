---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-doctor-shape-adr]]"
---



# `cli-workflow-redesign` adr: `app overview shape` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The redesigned CLI needs a single operational read surface for the active tax
workflow. Today, overview only exposes `status`; calendar behavior is hidden
behind a flag; the legacy deadlines package exists but is unmounted; and the
phantom roleplay `status` family has no locked grammar.

Without an explicit overview ADR, the redesign risks recreating root
`deadlines`, root `status`, or app-scoped bucket/history commands that violate
the two-root contract and the bucket ADR.

## Considerations

The existing application overview layer already produces typed calendar data
and readiness/completeness warnings. The existing deadline engine is usable as
the source of calendar entries, but it still lacks festivo and business-day
shift support.

The bucket-event-history ADR requires app status/list views to summarize
material events while keeping full event browsing under
`aeat config bucket history`.

The legacy deadlines CLI reads profile data from `--profile` and
`AEAT_DEFAULT_PROFILE_PATH`, and it renders through Rich-only code. Those paths
do not match the redesign's active workflow/profile state and `_emit` output
contract.

## Constraints

- Root command shape remains exactly `aeat config` and `aeat app`.
- No root `aeat status` or root `aeat deadlines` command is retained.
- Overview is read-only and does not emit bucket events for normal reads.
- Full event browsing stays under `aeat config bucket history`.
- Every overview command supports `--format json` through `_emit`.
- Redesigned overview commands read active workflow/profile state and active
  bucket state; they do not use `--profile PATH` or `AEAT_DEFAULT_PROFILE_PATH`.
- No compatibility shims or legacy command aliases are added.

## Implementation

`aeat app overview` is the operational read surface over the active profile and
active bucket.

The accepted grammar is:

```text
aeat app overview status
    [--period PERIOD]
    [--verbose]
    [--format json|text]

aeat app overview calendar
    --from YYYY-MM-DD
    --to YYYY-MM-DD
    [--allow-incomplete]
    [--format json|text]

aeat app overview agenda
    [--date YYYY-MM-DD]
    [--allow-incomplete]
    [--format json|text]

aeat app overview backlog
    [--from YYYY-MM-DD]
    [--to YYYY-MM-DD]
    [--format json|text]

aeat app overview explain MODELO
    [--year YYYY]
    [--format json|text]
```

Migration mapping:

- `aeat deadlines list --year YYYY` becomes
  `aeat app overview calendar --from YYYY-01-01 --to YYYY-12-31`.
- `aeat deadlines next --year YYYY` becomes `aeat app overview agenda` with
  `next_due` in the payload.
- `aeat deadlines explain MODELO` becomes `aeat app overview explain MODELO`.
- Phantom `status show` becomes `aeat app overview status`.
- Phantom daily-status view becomes `aeat app overview agenda`.
- Phantom `backlog show` and `backlog scaffold` become
  `aeat app overview backlog`.

JSON output uses stable typed objects:

- `status` includes active profile, bucket id, profile readiness, ledger
  summary, purchase-evidence summary, payable/collectible operation summary,
  draft summary, unreadable-row summary, next actions, and recent events.
- `calendar` uses the current overview calendar shape with range, entries,
  generated-at, warnings, and completeness.
- `agenda` includes as-of date, due on date, due soon, overdue, next due, blocking
  items, next actions, and recent events.
- `backlog` includes range, items, counts by kind, blockers, next actions, and
  recent events.
- `explain` includes modelo, year, applicability, rationale, and profile facts
  used.

The current `_profile_to_autonomo()` adapter is an interim bridge and must be
removed when the active-workflow-state migration lands. Readiness-sensitive
views must not silently default missing identity data.

## Rationale

Overview is the right place for cross-domain read models because it tells the
operator what the active bucket needs next without owning mutations. Deadline
calendar, agenda, readiness, and backlog all combine profile, bucket, ledger,
modelo, diagnostics, and event state; splitting them across root status or
deadlines commands would make the two-root model harder to reason about.

Keeping event browsing in `config bucket history` preserves the storage/history
boundary while allowing overview to show recent event summaries that explain
why a workflow is blocked.

Rejecting legacy profile-path and Rich-only deadline code prevents the new
surface from carrying stale `setup` era assumptions into the active-bucket
workflow.

## Consequences

The legacy `entrypoints/cli/deadlines` package is migrated into overview
commands or deleted. It is not remounted as a root or compatibility surface.

`aeat app overview status --calendar` is replaced by a first-class
`aeat app overview calendar` command.

`aeat app overview agenda` becomes the home for "next deadline" and "what needs
attention now" output.

`aeat app overview backlog` is a read model only. Import and workflow
continuation behaviors are excluded from this surface; lifecycle continuation
is owned by `aeat app modelo resume` per the workflow-resumption-semantics
ADR.

`status history` is rejected here; history is satisfied by
`aeat config bucket history` and `aeat app modelo history`.

Production-grade calendar/agenda semantics use the festivos and business-day
deadline-shift rules.

## 2026-05-15 amendment - separate verb tree ratification

The 2026-05-15 ground-truth audit found that only `aeat app overview
status` shipped; `calendar`, `agenda`, `backlog`, and `explain` were
left as flag axes on `status`. This amendment ratifies the **separate
verbs** decision: `aeat app overview` exposes five top-level verbs:

- `status` - composite roll-up (kept as the single bare-invocation
  entry point; surfaces a brief calendar / agenda / backlog summary).
- `calendar` - period-keyed deadline calendar with festivos
  shift-deadline applied; supports `--year` / `--modelo` / `--period`
  optional filters per the W70.P336 list-vs-query semantics.
- `agenda` - upcoming-deadline ranking with a top-of-payload
  `next_due` field; `--horizon` controls the window.
- `backlog` - past-due / missing-prerequisite / triage cohort listing.
- `explain` - per-(modelo, period) decomposition of required inputs,
  binding sources, and current readiness flags.

`status` retains a brief composite roll-up but does not gate
discoverability of the other four. Lifecycle continuation remains
owned by `aeat app modelo resume` per the workflow-resumption-semantics
ADR; `aeat app overview` does not own resume.
