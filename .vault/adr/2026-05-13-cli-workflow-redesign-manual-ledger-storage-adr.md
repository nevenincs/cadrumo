---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-research]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` adr: `manual ledger transaction entry and bucket-scoped ledger storage` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

Manual ledger transactions are first-class application data. They are not provider-import leftovers, review annotations, or temporary overlays on imported rows. Operators need to record cash movements, corrections, non-provider transactions, and evidence-backed tax facts directly in the active profile bucket.

The current transaction catalogue boundary is not profile-bucket scoped. Review/edit behavior can annotate workflow state, but aggregation reads transaction catalogue fields. Exposing manual entry before the catalogue resolves through the active profile bucket would make operator-created rows globally shared, collision-prone, and potentially invisible or incomplete for modelo aggregation.

## Considerations

- Profile bucket persistence already established that profile values live behind the active profile pointer and `PROFILE_BUCKET_NAMESPACE`.
- The transaction catalogue currently uses a static namespace and object key, so bucket identity is not enforced by the repository boundary.
- Transaction identity is content-derived and does not include bucket identity, which is unsafe for repeated manual entries and cross-bucket duplicates.
- Review annotations are useful operator state, but they are not the persisted transaction facts consumed by Renta aggregation.
- Bucket event history exists as an append-only ledger, but ledger transaction event names and object types still need explicit enum and emission support.
- Usage ratios support business/private proportionality for ledger facts. IVA prorrata is a separate VAT substrate and must not be collapsed into usage-ratio storage.
- Per-modelo aggregation must receive normalized, bucket-local source facts, not global catalogue rows presented as active-bucket rows by the operator surface.

## Constraints

- Manual ledger transactions MUST persist through a bucket-scoped transaction catalogue resolved from the active profile bucket.
- Manual entry, import, edit, delete, archive, and export MUST NOT be production-usable until transaction catalogue repository contracts are bucket-scoped.
- Manual entries MUST be stored as `ledger_transaction` facts, not as review overlay records.
- Manual mutation APIs MUST write aggregation-visible transaction fields, including date, amount, currency, direction, counterparty or narrative, business classification, business percentage for mixed-use rows, spending category, taxable base, IVA rate or IVA amount where applicable, usage-ratio or proportionality references, prorrata-relevant references where applicable, evidence references, provenance, and audit metadata.
- Direction and zero-amount semantics MUST be resolved in backend validation before exposing operator input. Transfer, correction, and zero-value evidence cases need explicit policy.
- Bucket event history MUST record manual creation, import, edit/classification, allocation, evidence attachment, deletion, archive, and export events with structured payloads.
- CLI commands MUST be thin adapters and MUST NOT infer or synthesize tax facts that belong in backend contracts.
- Retired `financial` or `data` surfaces MUST NOT become compatibility entrypoints for manual ledger entry.

## Implementation

Adopt manual ledger transactions as a backend-owned ledger capability under the active profile bucket.

The transaction catalogue repository gains an active-bucket resolution contract before any lifecycle command is considered production-usable. The repository may encode bucket identity through namespace, object key, payload field, or a composed bucket-aware storage adapter, but the externally visible contract is that all transaction catalogue reads and writes operate on one active bucket unless an explicit storage-maintenance command asks for another bucket.

Transaction identity is revised so manual rows and imported rows are unique within the bucket-scoped catalogue and do not collide across buckets. The identity contract must support repeated cash payments, corrections, operator-entered rows with similar narratives, and imported rows that would otherwise hash to the same global id.

Manual-entry APIs persist a complete transaction fact, including:

- movement fields: transaction id, date, amount, currency, direction, counterparty, narrative, and period context where supplied
- tax fields: taxable base, IVA amount, IVA rate, IRPF or spending category, and model-relevant classification
- proportionality fields: business classification, `business_pct`, allocation rationale, usage-ratio reference, and any prorrata substrate reference required by VAT aggregation
- evidence fields: canonical `purchase_invoice_evidence` reference and supplementary attachment references where available
- provenance fields: manual/import/provider source, actor or command source, import batch where relevant, edit lineage, archived or deleted state, and audit event ids

Review/edit commands may render and guide operator workflow, but catalogue mutation APIs own the durable facts. Review overlays can point at transaction ids and record workflow annotations only when they do not replace catalogue state.

Bucket events add ledger transaction object support and explicit event names for manual creation, provider import, field edit, classification, allocation, evidence attachment or replacement, deletion, archive, and export. Event payloads include bucket id, transaction id, actor/source command, before/after summary where appropriate, validation outcome, timestamp, and referenced evidence or ratio ids.

The CLI exposes manual lifecycle commands only after backend contracts exist. The eventual operator surface belongs under `aeat app ledger` and may include create/add, edit, classify, allocate, attach, delete/archive, review, list, check, preflight, and export flows, but each command delegates to the centralized backend service and renders backend results through the standard emitters.

The implementation plan should gain a bespoke nested wave for this decision after profile bucket storage hardening and before broad downstream profile/schema or ledger command expansion. That placement keeps active-profile bucket persistence as the prerequisite and prevents downstream aggregation, profile schema, review, or ledger command work from building on the current global transaction catalogue. Exact wave and step identifiers are left to the plan CLI after approval.

## Rationale

Manual ledger entry is not a convenience wrapper around import. It is a primary source of accounting facts for cases where no provider feed exists or where the operator must record a cash transaction, correction, proportional allocation, evidence-backed expense, or model-relevant tax detail directly.

Making manual entries first-class prevents review annotations from becoming an accidental persistence layer. Aggregation already consumes catalogue fields, so durable manual facts must live in the same transaction substrate that aggregation and ledger preflight read.

Bucket-scoped storage is the critical ordering constraint. If commands are exposed while the transaction catalogue remains global, the active-profile UX can appear correct while storing rows in shared state. That would break profile isolation, duplicate handling, audit trails, and modelo input provenance.

Separating usage ratios from IVA prorrata also preserves legal meaning. Business/private proportionality can attach to ledger rows through usage-ratio context, while VAT prorrata remains an IVA aggregation substrate for the modelos that require it.

## Consequences

- Manual ledger entry is blocked on bucket-scoped transaction catalogue contracts.
- Import, edit, delete, archive, export, review, and aggregation paths must resolve ledger transactions through the active profile bucket before they are considered complete.
- The transaction model or repository contract must change to represent bucket-local identity and manual provenance safely.
- Bucket event enum and object-type support must expand for ledger transaction mutations.
- The current review overlay cannot be treated as the durable source for classification, category, base, IVA, or proportionality facts.
- Aggregation work can rely on manually entered rows only after those rows persist aggregation-visible fields in the bucket-scoped catalogue.
- CLI work follows backend implementation and remains thin; no manual ledger command should land as a CLI-local data writer.
- The active implementation plan needs a nested wave placed after profile bucket storage hardening and before broad downstream profile/schema or ledger command expansion.
