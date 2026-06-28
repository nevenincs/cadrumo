---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-research]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-08-cli-backend-boundary-reference]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
  - "[[2026-05-08-ledger-renta-pipeline-reference]]"
  - "[[2026-05-08-ledger-renta-pipeline-adr]]"
---



# `cli-workflow-redesign` adr: `ledger transaction management` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The historical app surface exposes ledger, generic invoice, and legacy financial command
surfaces that mix three concerns: transaction movement workflow, evidence
handling, and business-operation settlement. This makes operator intent and
audit readiness hard to reason about for model-bound fiscal preparation.

Ledger ownership must cover classify, allocate, attach, check, and export
instead of splitting those concerns across legacy surfaces. This ADR hardens
ownership and enforces gates, not just command intent.

The `financial invoices` entrypoint is part of the problem surface. It presents
list/show/link/reconcile/verify commands as a finance invoice domain, but those
operations combine ledger reconciliation, evidence linking, data quality checks,
and business-operation invoice handling. That conflation must not become the
approved app UX.

## Decision

`aeat app ledger` is the canonical transaction-management command family for
`ledger_transaction` movement facts. It owns the end-to-end chain from ingest to
model-ready export:

- provider ingestion with diagnostics and duplicate protection
- listing and status visibility
- review and classification, including `split` and `business_pct`
- category and readiness state required for deductible, VAT/IVA, and IRPF
  preparation: `category`, `business_pct`, `taxable_base`, rates, and
  proportionality context
- attachment and evidence lifecycle for each transaction through
  `purchase_invoice_evidence`, plus optional supplementary attachments
- links to business-operation objects: `payable_invoice` and
  `collectible_invoice`
- `ledger_sanitization`, complete/modelo verification, and export

`invoice` is not a primary ledger design concern. Receipts and supplier purchase
invoices can be attached to a ledger transaction as `purchase_invoice_evidence`
for deductible expense support. Issued income invoices, payable invoices, and
collectible invoices are business-operation/modelo objects. They may explain
why money is owed or later paid, and their payments may appear as ledger
transactions, but they are not ledger transaction rows.

## Considerations

The backend already has transaction import, merge, idempotency, diagnostics,
classification, and catalogue primitives. These functions must be wired into
ledger commands; duplicated CLI-specific finance flows are rejected.

Attachment manifests already support evidence-style links. The CLI must
expose that capability as ledger evidence work; a generic invoice workflow
is rejected.

Renta and modelo aggregation already consumes repository-backed transaction and
invoice-related facts. That aggregation belongs at the ledger-to-modelo
handoff, not inside an ad-hoc `financial invoices` command.

For autonomo IRPF workflows, issued income invoices are calculation-relevant
business-operation objects. A later bank receipt may become an incoming
`ledger_transaction`, but the issued invoice and the bank transaction are still
different objects with different roles.

## Constraints

- No `financial` command family may own primary transaction-flow UX.
- No generic `invoice` command may be treated as an approved ledger-management
  workflow.
- Ledger output must use `ledger_transaction` for movement facts.
- Deductible-expense evidence must use `purchase_invoice_evidence`.
- Business-operation invoice objects must use `payable_invoice` and
  `collectible_invoice` source kinds.
- Ledger mutation and sanitization must be bucket-scoped and event-history
  traceable.
- Live AEAT filing remains outside this decision. Ledger export is a prepared
  internal artifact for calculation workflows, not a live submission step.

## Invariants

- `ledger_transaction` evidence policy is one canonical record: at most one
  primary `purchase_invoice_evidence` per row. A second canonical assignment
  must fail with a CLI/domain validation error unless explicitly replaced.
- Supplementary attachment manifests are allowed for receipts, photos, notes,
  or additional references, but only one evidence anchor is canonical per row.
- Model-ready rows require class/category consistency. Mixed-use rows require a
  valid `business_pct` and split rationale before export.
- Tax readiness requires explicit taxable base, VAT/IVA amount or rate where
  relevant, IRPF category, and proportionality context before modelo
  calculation consumes the row.
- `purchase_invoice_evidence` is evidence only. `payable_invoice` and
  `collectible_invoice` remain business-operation objects.

## Verification Contract

- `ledger_sanitization` is mandatory before export and before any modelo verify
  path.
- `aeat app ledger preflight --mode complete` requires a full
  `transaction_aggregation_trace` and must fail with complete source-trace
  output for all blocked rows.
- `aeat app ledger preflight --mode modelo --modelo ...` also requires a full
  `modelo_input_graph`, plus readable failure traces for missing category,
  taxable base, rate, split, evidence, or proportionality readiness.
- Double-count prevention must run before modelo handoff. Orphan evidence links,
  non-reciprocal links, multi-link canonical evidence, amount mismatches, and
  unsupported evidence kinds are blockers, not warnings.

## Verb naming (apex review 2026-05-12)

Operator-facing verbs use plain-language names. The earlier drafts'
verbs `split`, `evidence`, and `sanitize` are renamed for discoverability and
to avoid destructive/legal connotations:

- `split` → `allocate` (records `business_pct` and allocation rationale; the
  prior "split" framing implied row-splitting semantics, which the verb does
  not perform).
- `evidence` → `attachments` (inspects, replaces, verifies, removes, or
  repairs the canonical `purchase_invoice_evidence` anchor and supplementary
  attachments; the prior "evidence" framing was legal-jargon and confused
  operators).
- `sanitize` → `check` (emits structured blockers and trace output; the verb
  is report-only and must not imply data destruction).

The backend source-kind name `purchase_invoice_evidence` is unchanged; only
the operator-facing CLI verb that manages it is renamed. Backend trace names
such as `ledger_sanitization` may keep their internal identity; their
operator-visible label is "check report".

## Implementation

`aeat app ledger` command scope is:

- `aeat app ledger import`: idempotent ingest with diagnostics.
- `aeat app ledger list`: list movement facts with filters.
- `aeat app ledger status`: summarize completeness, review state, and check
  blockers.
- `aeat app ledger review`: inspect row state.
- `aeat app ledger classify`: write classification through backend services.
- `aeat app ledger allocate`: record `business_pct` and allocation rationale.
- `aeat app ledger attach`: attach receipts, purchase invoice evidence, or
  reference material to the selected transaction.
- `aeat app ledger attachments`: inspect, replace, verify, remove, or repair
  the canonical attachment anchor and supplementary attachments.
- `aeat app ledger link`: link a transaction to `payable_invoice` or
  `collectible_invoice` where payment/receipt traceability is needed.
- `aeat app ledger check`: emit structured blockers and trace output.
- `aeat app ledger preflight`: support `--mode complete` and `--mode modelo`.
- `aeat app ledger export`: emit sanitized facts for backend model preparation.

The `verify` verb was renamed to `preflight` to avoid collision with the
`aeat app modelo verify` lifecycle gate. Operator help text for `check` and
`preflight` distinguishes them:
- `check`: "Report data-quality blockers for the active bucket (report-only,
  no mutations)."
- `preflight`: "Confirm ledger data is ready for modelo calculation. Use
  `check` first to fix quality issues, then `preflight --mode modelo
  --modelo M` to confirm modelo-specific readiness."

Backend wiring is mandatory:

- import and diagnostics route through `import_ledger_with_diagnostics`,
  `derive_transaction_id`, and repository merge/duplicate policy.
- split and classify transitions route through transaction services and domain
  validation.
- evidence operations route through attachment and secure-envelope services in
  bucket storage.
- verification routes through `ledger_sanitization`,
  `transaction_aggregation_trace`, and `modelo_input_graph` builders.
- business-operation links route through backend linking services; these are
  semantic links, not transaction substitutes.
- modelo preparation routes through repository-backed aggregation and model-safe
  binding resolvers.

The existing generic invoice surfaces must be removed:

- `_invoice.py` is removed from operator-facing CLI surfaces. Its behavior is
  split into explicit business-operation commands and ledger evidence/link
  commands.
- `financial/invoices.py` is not an approved primary UX surface. Its link,
  reconcile, verify, and unmatched flows must be split into ledger
  sanitization/evidence commands or modelo/business-operation commands.
- `financial/txs.py` classification and LLM orchestration must become thin
  transport over backend services or be moved under the approved ledger command
  family.
- `financial txs`, `_invoice.py`, and `financial/invoices.py` must not remain
  executable, callable, imported by `entrypoints/cli`, or listed in public
  help. No primary or support-only transaction workflows may be introduced
  there.

## Rationale

Users manage transactions before they calculate modelos. The ledger CLI should
therefore describe what the user is actually doing: importing bank or payment
movements, reviewing them, adding evidence, classifying them, fixing data
quality problems, and producing sanitized facts for calculations.

This keeps purchase receipts and supplier invoices in their correct role as
evidence for expense transactions. It also keeps issued income invoices and
payable/collectible invoices in their correct role as business-operation objects
that modelo calculations may consume.

## Consequences

The CLI redesign must stop treating generic invoice paths as equivalent to
ledger management. Any remaining use of broad invoice terminology must be
removed from operator UX or explicitly tied to a business-operation/modelo
domain.

Ledger completion now requires a visible sanitize step before modelo
calculation handoff. Modelo commands can depend on ledger facts only after the
ledger backend has made source kind, evidence, classification, split, and
quality state explicit.

The implementation plan must include command migration, translation/help text
updates, backend service wiring, and tests proving that ledger transaction
management, purchase evidence, business-operation invoices, and modelo
calculation inputs remain separate.

## 2026-05-14 amendment — test-user audit finding P0 #3 (transaction identity)

Audit observation: `aeat app ledger list` and `aeat app ledger review` print
8-character transaction-id prefixes, while every mutating verb (`read`,
`classify`, `edit`, `allocate`, `attach`, `archive`, `stash`, `remove`)
demands the full 64-character hex hash. Operators have no in-CLI path from a
listed row to an actionable identifier other than exporting CSV. This makes
the ledger workflow unusable for its primary user-journey.

Rule:

- Transaction identity has two surfaces: a `full_id` (the canonical
  64-character hex hash used by all backend services) and a `display_id` (a
  short, ambiguity-checked prefix used solely for human-readable rendering).
- `aeat app ledger list`, `review`, `show`, and any other read leaf MUST
  render BOTH `display_id` AND `full_id` columns in `--format text` and BOTH
  fields in `--format json`. The text rendering MUST NOT hide `full_id`
  behind a flag; it is the default column set.
- All mutating leaves (`read`, `classify`, `edit`, `allocate`, `attach`,
  `archive`, `stash`, `remove`, and any future evidence verbs) MUST accept
  either a `full_id` or any unambiguous prefix of one. The backend service
  resolves the prefix; on collision the CLI MUST refuse with a validation
  error that lists the matching `full_id` set.
- The `display_id` width is a backend-decided property of the active bucket
  (minimum length required to keep all current rows uniquely addressable).
  It MUST NOT be a hardcoded constant of 8 characters; it grows automatically
  as the bucket fills.
- `--format json` payloads MUST always carry the canonical `full_id` field
  name; `display_id` is presentation only and MUST NOT be the JSON key.
- This is the target shape. No `--full-id` opt-in flag, no `--no-truncate`
  flag, no "legacy short-only" mode.

Acceptance criteria:

- A user can pipe `aeat app ledger list --format text | tail -n 1` into
  `xargs aeat app ledger classify --transaction-id ...` without re-querying.
- A 10-character prefix that uniquely identifies one transaction resolves;
  an 8-character prefix that matches two transactions refuses with a typed
  validation error and lists the collisions.
- JSON output for every ledger leaf has `full_id` keys, never `id` aliased
  to a truncated prefix.

## 2026-05-14 amendment — test-user audit finding P0 #4 (evidence ingest surface)

Audit observation: `aeat app ledger attach --purchase-invoice-evidence-id`
requires an evidence record id, but there is no CLI verb that constructs
such a record. No `aeat app receipts`, no `aeat app invoices add`, no
`aeat app evidence` exists. A user cannot attach a single supplier receipt
to a single transaction with the redesigned CLI.

Rule:

- `aeat app ledger evidence` is the locked noun-group name. Its CRUD
  subcommands are exactly `add`, `remove`, `update`, `view`, and `list`.
  No alternate spelling is approved. `aeat app ledger evidence add` is the
  construction verb; it consumes the PDF/image source described by the
  receipt-ocr-pdf-evidence ADR and returns the
  `purchase_invoice_evidence_id`.
- File-type scope is restricted to PDF and image inputs handled by the OCR
  path defined in the receipt-ocr-pdf-evidence ADR. Plaintext, email body,
  and Drive-URL evidence sources are explicitly out of scope; their
  expansion is deferred to a future `evidence-source-expansion` ADR.
- `aeat app ledger attach --purchase-invoice-evidence-id <id>` continues to
  consume the id produced by `aeat app ledger evidence add`. The flag name
  is unchanged.
- No third CLI root is created; the noun group is nested under
  `aeat app ledger`, in keeping with the two-root invariant.
- `aeat app ledger attach --help` MUST surface
  `aeat app ledger evidence add` by name as the discoverable upstream of
  `--purchase-invoice-evidence-id`. Help text is the discovery path; a user
  reading `attach --help` must see how to produce the id it requires.
- The previous `attachments` inspection group is subsumed by the locked
  `evidence` group; its `view`, `list`, `remove`, and `update` verbs cover
  the inspection and replacement surface.

Acceptance criteria:

- `aeat --help`, `aeat app --help`, `aeat app ledger --help` chain leads a
  user from "I have a receipt PDF" to `aeat app ledger evidence add` as
  the single visible verb that creates a `purchase_invoice_evidence`
  record.
- All five CRUD verbs (`aeat app ledger evidence add`,
  `aeat app ledger evidence remove`, `aeat app ledger evidence update`,
  `aeat app ledger evidence view`, `aeat app ledger evidence list`) are
  registered, discoverable through `aeat app ledger evidence --help`, and
  each accepts `--format json|text` through `_emit`.
- A smoke run `aeat app ledger evidence add ./some.pdf` followed by
  `aeat app ledger attach --id <full> --purchase-invoice-evidence-id
  <evidence-id>` completes end-to-end.
- Non-PDF/image evidence sources (plaintext, email body, Drive URL) refuse
  at the construction boundary with a typed validation error that points
  at the deferred `evidence-source-expansion` ADR.
- No third CLI root is introduced; no `aeat receipts`, `aeat invoices`, or
  `aeat evidence`.
