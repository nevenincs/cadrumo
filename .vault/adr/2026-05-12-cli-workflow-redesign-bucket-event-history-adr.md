---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-design-research]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-calculate-revisions-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-verify-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-verified-complete-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---



# `cli-workflow-redesign` adr: `Bucket event history` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The bucket model requires an auditable history of material workflow changes.
Without bucket-scoped event history, the backend cannot explain when a profile
bucket was created, which data imports changed the ledger, which modelo revision
was calculated or verified, when a filing record was created, or when export and
submission statuses changed.

## Considerations

- A bucket is the storage slice associated with the active profile.
- Profile data itself is stored in its bucket.
- Ledger, modelo calculation, verification, filing, export, and submission
  status changes all need durable audit context.
- CLI status and troubleshooting need a chronological view of what happened in a
  bucket, not only the latest record state.
- Filing records already require history events, but the event-history backend
  is a missing capability and must be designed as a shared bucket service.
- The CLI surface for browsing bucket event history belongs under
  `aeat config bucket`, not under `aeat app`.
- Bucket history browsing is a storage inspection and diagnostic capability.
  Normal app UX must summarize material events in relevant status/list views so
  operators can understand workflow progression without opening full bucket
  history first.

## Constraints

- Bucket event history is append-only.
- Events are scoped to a bucket id and must use immutable ids.
- Events must record timestamp, event type, actor or command source, command
  context, and target object references.
- Events must not be used as the only source of relational truth. Domain tables
  still own current state; events explain state transitions.
- Event payloads must be structured and versioned so the CLI can render stable
  history output over time.
- Events must preserve references to affected profile records, ledger imports,
  ledger financial transactions, payable invoices, collectible invoices,
  purchase invoice evidence, modelo work units, calculation revisions,
  verification reports, filing records, exports, and submission-status changes
  when those objects are involved.
- App status/list summaries that show event context are mandatory for material
  workflow states and must include, at minimum: timestamp, event type, object
  type, object id/revision, actor/source, and outcome/state.
- Events must not record secrets or raw credentials.
- The event-history backend must not create an `aeat app bucket` command.

## Implementation

- Add a bucket-scoped event-history storage capability.
- Define initial event families for profile and bucket lifecycle, ledger import
  and enrichment, modelo calculation, verification, filing, export, and
  submission-status tracking.
- Write events inside the same logical transaction as the domain state change
  where storage allows it.
- Expose full event history through `aeat config bucket history`.
- App-domain views such as `aeat app modelo status` and analogous domain
  status/list views must summarize material bucket events using the required
  minimum fields; they do not own bucket browsing or bucket management.
- App-domain commands emit bucket events as they change bucket contents; users
  do not need to invoke bucket commands for ordinary ledger/modelo workflows.
- Filing-record creation writes a `modelo.filed` event linked to the filing
  record and the filed calculation revision.
- Forward calculation after filing writes an event that records the filed-chain
  anchor and successor draft revision.

## Rationale

The workflow is accounting and tax oriented, so users need to know not only what
the current state is but how it got there. Append-only bucket events provide the
audit layer without replacing normalized relational records for ledger,
profile, modelo, and filing state.

## Per-service emission scope

The following domain and application services own material state transitions
that must emit bucket events:

- transactions service (ingest, classification, split, sanitization
  outcome) — events: `ledger.transaction.imported`,
  `ledger.transaction.classified`, `ledger.transaction.split`,
  `ledger.sanitization.completed`
- invoices service, split per the invoice-domain-decoupling taxonomy —
  events keyed by source kind: `payable_invoice.*`,
  `collectible_invoice.*`, `purchase_invoice_evidence.attached`
- attachments service — `purchase_invoice_evidence.attached`,
  `attachment.linked`, `attachment.removed`
- rental finca/contract repositories — `rental.finca.recorded`,
  `rental.contract.signed`, `rental.aggregation.recomputed`
- inventory ledger service — `ledger.inventory.created`,
  `ledger.inventory.movement_added`, `ledger.inventory.valuation_applied`
- assets ledger service — `ledger.assets.recorded`,
  `ledger.assets.amortization_applied`, `ledger.assets.disposed`
- profile actions — `profile.created`, `profile.activated`, `profile.set`,
  `profile.unset`, `profile.imported`, `profile.exported`
- auth actions — `auth.provider.configured`, `auth.session.opened`,
  `auth.session.closed`, `auth.apoderado.configured`
- filing calculate / verify / file pipeline — `modelo.calculation.created`,
  `modelo.verification.passed`, `modelo.verification.refused`,
  `modelo.filed`, `modelo.filed_superseded`, `modelo.amended`,
  `modelo.filing.imported`
- filing-history repository — `modelo.history.entry_recorded`
- review queue — `review.item.deferred`, `review.item.approved`
- live-read snapshot capture — `live.notifications.snapshot_captured`,
  `live.expedientes.snapshot_captured`, `live.borrador100.snapshot_captured`,
  `live.verify.nif_iva_checked`, `live.verify.tgvi_checked`,
  `live.filed.capture_created`

Each service's emission lands with its execution ADR/plan; this ADR fixes the
emission scope, the minimum payload fields, and the append-only contract.

## Consequences

- Backend storage work is required before bucket/modelo workflows can be called
  production-grade.
- Domain services must consistently emit events for material state transitions
  per the per-service emission scope above.
- CLI history/status output needs stable event rendering and filtering.
- Tests must prove that key domain writes create both relational state and the
  expected bucket event in the same workflow.
