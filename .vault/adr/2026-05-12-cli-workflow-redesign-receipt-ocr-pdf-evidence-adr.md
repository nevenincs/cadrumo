---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-research]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---

# `cli-workflow-redesign` adr: `receipt OCR PDF evidence` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.
## Problem Statement

`app ledger attach` needs a path for purchase receipts and purchase invoice
evidence, but the existing PDF parsing work targets AEAT filing justificantes,
not supplier evidence.

## Considerations

Purchase receipt OCR/PDF extraction supports ledger transaction evidence. It
must produce `purchase_invoice_evidence`, not a generic invoice and not a
modelo filing receipt.

## Constraints

Do not treat AEAT justificante parsing as receipt OCR. Do not emit bare
`invoice`. Do not use LLM/OCR extraction without stored evidence provenance.
Do not place justificante PDFs into casilla data.

## Implementation

Add an `app ledger attach` evidence adapter for receipt and purchase invoice
PDF/image inputs. Store the source file hash, extraction method, extraction
confidence, extracted fields, manual-review state, and transaction link inside
the active bucket.

The adapter emits `purchase_invoice_evidence` and records bucket events for
attachment creation, review, replacement, and removal.

## Rationale

Supplier evidence and AEAT filing receipts are different artifacts. Keeping
them separate protects filing-record semantics and gives ledger classification
the evidence it actually needs.

## Consequences

Ledger ingestion can be completed with traceable purchase evidence. Any OCR or
LLM output remains reviewable evidence, not an unproven calculation input.

## 2026-05-14 amendment — test-user audit finding P0 #4 (construction verb)

The receipt OCR adapter is a backend capability. The audit established that
no operator-visible verb exists to invoke it: `aeat app ledger attach
--purchase-invoice-evidence-id` consumes an id the CLI provides no path to
produce. This ADR closes that gap from the OCR side and the ledger-
transaction-management ADR closes it from the ledger group side.

Rule:

- The locked construction verb is `aeat app ledger evidence add`. It is one
  of the five CRUD verbs (`add`, `remove`, `update`, `view`, `list`) on the
  `aeat app ledger evidence` noun group. The verb accepts a source
  PDF/image path plus optional manual override fields, runs the OCR
  pipeline through the existing backend service, stores the evidence record
  in the active bucket, emits the documented `purchase_invoice_evidence`
  event, and prints the new evidence record's `full_id` on success.
- The adapter MUST NOT be exposed through a third CLI root, an `aeat
  receipts` family, or a flag on `attach`. The two-root invariant holds.
- The verb's `--format json` payload MUST surface the OCR confidence and
  manual-review state already specified by this ADR's implementation
  section, so downstream `review` and `classify` can act on them.

### Out-of-scope file types (deferred)

PDF and image inputs handled by the OCR path are the entire scope of this
ADR and of the W70 evidence-ingest delivery. Plaintext receipts, email-body
receipts, and Drive-URL evidence pointers are explicitly out of scope here
and are NOT delivered by any W70 phase; their construction surface is
deferred to a future `evidence-source-expansion` ADR. The
`aeat app ledger evidence add` verb MUST refuse non-PDF/image sources at
the construction boundary with a typed validation error that names the
deferred ADR. This fencing protects the W70 delivery from scope creep and
preserves the broader source set as a future decision rather than a lost
requirement.

Acceptance criteria:

- The verb exists, is discoverable through `aeat app ledger --help` and
  `aeat app ledger evidence --help`, and produces an evidence id that
  `aeat app ledger attach` accepts in the same shell session.
- A failure path (corrupt PDF, OCR refusal) raises through the central
  AeatError facilities defined in the apex CLI Backend Boundary section.
- A non-PDF/non-image source path (plaintext, email body, Drive URL) is
  refused with a typed validation error pointing at the deferred
  `evidence-source-expansion` ADR.
