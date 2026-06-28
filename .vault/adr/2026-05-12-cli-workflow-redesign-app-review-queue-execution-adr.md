---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-research]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
  - "[[2026-04-18-unified-review-queue-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---

# `cli-workflow-redesign` adr: `app review queue execution` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

The apex has one remaining child slot: execution of the unified review queue
under the redesigned CLI contract. The 2026-04-18 review ADR predates the
two-root design and must be adapted rather than copied forward.

## Considerations

The review backend substrate is shaped around old
source names, old drill commands, and a narrower set of emitted item kinds.
Embedded review/edit verbs in ledger, invoice, and declaration surfaces are
not canonical UX. Keeping those embedded surfaces as canonical UX would
preserve the fragmented review flow the queue was meant to replace.

Accounting and tax workflow products commonly separate passive status from
human review queues. Imported bank transactions, guessed explanations,
unreconciled statement lines, and tax-practice tasks are exposed as items that
need operator judgment before the books or tax workflow can be trusted. This
ADR uses `review` in that narrow sense only.

## Constraints

Root surfaces remain exactly `aeat config` and `aeat app`. No top-level
`aeat review` survives. No compatibility aliases, forwarding commands, or
hidden shims are retained. Output uses root `--format json|text` and `_emit`.
Bare `invoice` is not a review kind or command-copy term. Generic review
mutations are rejected from `app review`.

## Implementation

Implement `aeat app review` as a read-only cross-domain review mini-app:

```text
aeat app review queue
    [--kind ledger_transaction|purchase_invoice_evidence|payable_invoice|collectible_invoice|modelo_finding|live_notification|sync_divergence]
    [--state pending|all]
    [--modelo MODELO]
    [--source-kind KIND]
    [--format json|text]

aeat app review show REVIEW_ITEM_ID
    [--format json|text]
```

`queue` aggregates review items across the active bucket. `show` drills into
one item without mutating it. Both commands are read-only and emit no bucket
event.

Each queue row carries a stable review item id, review `kind`, separate
`source_kind`, affected object id, bucket id, optional modelo/period,
severity, state, blocking flag, reason, current owner surface, canonical next
command, and since timestamp. If an item cannot point to a real source object
and a real next command, it is not eligible for `app review queue`.

Replace legacy backend item kinds explicitly:

- `transaction` pending items become `ledger_transaction`.
- `invoice` pending items split into
  `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`.
- `finding` draft items become `modelo_finding`.
- `live_notification` and `sync_divergence` are reserved vocabulary for
  concrete live and sync review repositories.

`kind` is the review item kind. `source_kind` is separate: one of
`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, or
`collectible_invoice`, or null for modelo/live/sync items.

Update `ReviewItem.drill_command` values so they point to
`aeat app review show REVIEW_ITEM_ID` or to canonical non-review app actions.
They must not point to `financial`, `filing`, `sync`, top-level `review`, or
embedded review commands.

Generic `app review edit`, `app review approve`, `app review accept`,
`app review lock`, and `app review defer` are rejected. Source-specific
mutation lives under its owning app surface (`app ledger`, `app modelo`).
Generic review mutations are not exposed through this surface.

## Rationale

This closes the open child slot while preserving the redesign boundaries. The
operator gets one place to answer what needs attention, but the ADR does not
invent unsafe cross-source mutations before bucket events and source-kind
semantics are fully designed.

The name `review` is accepted because the surface is explicitly about human
judgment. It is not `overview status`: status is a passive summary. It is not
`overview backlog`: backlog is pending work inventory. Review is the actionable
decision queue for records that need inspection, confirmation, classification,
or correction before calculation, verification, or internal file approval can
be trusted.

## Consequences

The apex §4.6 surface becomes locked as read-only `aeat app review queue` and
`show`. The old top-level `aeat review queue` placement is superseded.
Embedded review commands are implementation harvest only, not canonical UX.
Tests must assert command registration, absence of retired roots, absence of
generic mutation verbs, root `--format` behavior, source-kind output, and
updated drill commands. Replace tests that lock legacy `transaction` /
`invoice` / `finding` kinds or old drill-command paths.

## 2026-05-14 amendment — test-user audit finding P2 #9 (fresh-profile severity)

Audit observation: on a freshly-installed profile, `aeat app review queue`
surfaces ~20 `critical` findings sourced from 13 mystery `borradores` that
exist in the bucket on first run. Treating those records as critical when
the operator has not yet done any work misrepresents the system state on
first contact.

Rule:

- Legacy `borrador` records present in the bucket at profile initialization
  time MUST be auto-classified into a `legacy-borrador` cohort by the
  initialization service. Cohort assignment is a backend property, not a
  CLI flag.
- The review-queue execution surface MUST demote the `legacy-borrador`
  cohort below `critical` severity by default. The cohort surfaces as
  `info` severity unless an operator explicitly bumps it.
- A separate verb (the existing `app review` group's drill paths are
  acceptable; the spelling is for the implementation step to pick) MUST
  let the operator inspect, accept, or quarantine the cohort.
- The cohort assignment is recorded as a bucket event so subsequent
  reviews see the source of the demotion.
- This is the target shape. No backward-compat path is preserved; profiles
  that initialize after this change ship with the cohort already
  classified. Pre-existing profiles see the cohort assigned on next
  `aeat config repair` or equivalent migration step.

Acceptance criteria:

- A smoke run of `aeat config init` followed by `aeat app review queue` on
  a fresh profile emits zero `critical` findings sourced from
  `legacy-borrador` records.
- The cohort drill verb returns the legacy records and labels their
  cohort.
