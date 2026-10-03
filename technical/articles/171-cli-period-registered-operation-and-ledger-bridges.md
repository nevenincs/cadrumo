# CLI period, registered-operation, and ledger bridges

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-171` · **Topic:** [Operator interfaces, part 2: secure transport and operation bridges](../topics/operator-interfaces-part-2.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 41 CLI modules spanning 6,114 source lines and 47,996 measured `o200k_base` proxy tokens. I read the full assigned ranges in nine bounded helper pages, including the split file continuations; there are no intentionally unread slices. The review is static and describes these adapters and contracts only. It does not execute the CLI or workers, establish runtime correctness, inspect external authority freshness, or certify legal calculations. The main areas are period-token parsing; the common registered-operation transport and review protocol; collaboration, diagnostics, filing and IVA evidence capture; and ledger transaction, invoice-evidence, asset, and follow-up commands.

## Capabilities and operation flow

The period parser gives CLI callers a narrow vocabulary for tax periods. It accepts explicit year-qualified annual, quarter, month, and supported special-period forms, resolves them into domain periods, and returns structured parse failures with accepted forms rather than treating arbitrary text as a date. This keeps display-token parsing at the boundary and lets downstream commands receive typed periods (`period_parsing.py` (`src/cadrumo/entrypoints/cli/period_parsing.py`)). The exact accepted span and normalization behavior are local to this module; callers and form-model semantics should be checked before inferring which periods a complete workflow supports.

The registered-operation modules form the shared CLI-to-worker boundary. They construct and admit a request against a registered definition, encode and exchange the request through the retained frontend client, poll and interpret operation observations, validate a terminal completion and its result schema, and correlate reviews and responses with the pending operation. Contracts carry definition and request/result versions, the exact profile subject, and typed projections; refusal detail is only exposed under explicit command opt-in and declared refusal conditions. The helper separates terminal success, refusal, and uncertainty. In particular, timeouts or incomplete/ambiguous observations remain uncertain instead of being presented as a refusal, and the deadline helpers reserve a small read budget for final state retrieval. Review responses must match the pending reference and revision/schema/interaction context before the CLI submits a decision (`registered_operation_admission.py` (`src/cadrumo/entrypoints/cli/registered_operation_admission.py`), `registered_operation_completion.py` (`src/cadrumo/entrypoints/cli/registered_operation_completion.py`), `registered_operation_exchange.py` (`src/cadrumo/entrypoints/cli/registered_operation_exchange.py`), `registered_operation_observations.py` (`src/cadrumo/entrypoints/cli/registered_operation_observations.py`), `registered_operation_reviews.py` (`src/cadrumo/entrypoints/cli/registered_operation_reviews.py`)). This common layer is the strongest local safety mechanism in the chunk: command-specific code relies on a correlated operation receipt rather than trusting a returned payload by itself.

Several smaller bridges expose profile-owned collaboration and diagnostics. Recipient add/remove flows bind the active profile and check the worker’s updated recipient set; list operations are read-only. Counterparty lookup uses its registered operation. Diagnostics request an exact diagnostic kind and bounded result and accept only the expected result arm with no state effect. The helper code establishes request/result correlation, while the diagnostic data’s collection and redaction behavior are owned by the worker and are not independently established here (`runtime_collab_recipient.py` (`src/cadrumo/entrypoints/cli/runtime_collab_recipient.py`), `runtime_counterparty.py` (`src/cadrumo/entrypoints/cli/runtime_counterparty.py`), `runtime_diagnostics.py` (`src/cadrumo/entrypoints/cli/runtime_diagnostics.py`)).

The filing and IVA adapters submit profile-scoped operations to capture declarations, filed reports, filing receipts, IVA history, remote state, and wallet evidence. Companion readers return locally stored snapshots or profile-bound lists, validate identity, period, count, schema, and effect, and rebuild the established CLI result shapes. These distinguish external capture operations from local read commands; a successful capture means the registered operation reported a correlated result, not that an authority’s data or a legal conclusion was independently verified. Some capture flows permit `UPDATED` where refresh or saved evidence can occur; exact persistence semantics live in the worker and should be traced there (`runtime_expedientes_capture.py` (`src/cadrumo/entrypoints/cli/runtime_expedientes_capture.py`), `runtime_filed_bulk.py` (`src/cadrumo/entrypoints/cli/runtime_filed_bulk.py`), `runtime_filed_read.py` (`src/cadrumo/entrypoints/cli/runtime_filed_read.py`), `runtime_iva_remote_state_capture.py` (`src/cadrumo/entrypoints/cli/runtime_iva_remote_state_capture.py`), `runtime_justificante_read.py` (`src/cadrumo/entrypoints/cli/runtime_justificante_read.py`)).

The ledger surface is broader. It supports adding and allocating transactions, applying typed classification patches (including selected M210 facts and operator IVA derivation), bulk CSV classification, checks, and attachment/detachment. These bridges bind a profile, send typed requests and compare the worker result with input identity and receipt effect. The add request carries dates, money, direction, description/counterparty, business use, classification, IVA, deduction/investment and IRPF details, prorrata references, source jurisdiction, invoice evidence and attachment identifiers, actor and idempotency key; the CLI boundary does not itself perform the full tax calculation. Attachment commands verify that requested evidence appears or requested removals disappear, and compare event presence with `UPDATED` versus `NONE` (`runtime_ledger_add.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_add.py`), `runtime_ledger_allocate.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_allocate.py`), `runtime_ledger_classify.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_classify.py`), `runtime_ledger_attachment.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_attachment.py`)). Bulk classification intentionally converts invalid/oversized request validation to a generic invalid-frame refusal so parser details do not echo private CSV input; for success, the operation receipt owns the effect and the returned applied count only cross-checks it (`runtime_ledger_bulk_classify.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_bulk_classify.py`)).

Invoice support includes catalogue reads/mutations, local-file intake, manual wizard additions, adding purchase-invoice evidence, batch evidence ingestion, and document pulls. Intake resolves a local path and sends a digest to the worker; evidence addition correlates the returned source digest/attachment ID, media kind, invoice fields, keyed idempotent identity or ordinary ID shape, and write receipt. Follow-up operations list consent, review queues, and attachment metadata, or view one exact review item. Queue order, pending flags, profile identity and no-effect reads are checked. The consent result states that transmitted bytes are unrecallable; this is exposed as product data, not proof that all outbound paths or remote retention are covered by this bridge. A review view returns its full closed projection, so callers should treat those fields as potentially sensitive (`runtime_invoice_intake.py` (`src/cadrumo/entrypoints/cli/runtime_invoice_intake.py`), `runtime_ledger_evidence_add.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_add.py`), `runtime_ledger_evidence_followup.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_followup.py`), `runtime_ledger_evidence_ingestion.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_ingestion.py`)).

The activity-asset commands cover create/correct, inspect, forecast, claim/replay, and filing handoff. Forecast and handoff are framed as non-consuming reads, while a claim binds to the forecast and returns a correlated immutable claim. The bienes-inversión adapter lists and declares profile-owned investment goods and translates typed refusal reasons into CLI refusal messages. These are transport and projection responsibilities; calculation rules and durable mutation guarantees require tracing application/persistence modules (`runtime_ledger_actividad_asset.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_actividad_asset.py`), `runtime_ledger_bienes_inversion.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_bienes_inversion.py`)).

## Data, trust, and security

Requests generally take the profile UUID from the bound runtime client or active-profile pointer, set the registered subject from that identity, and then require profile and definition correlation on returned projections. Read operations usually require `NONE`; mutation operations derive expected effects from the requested action, returned event identifiers, or explicit worker effect, and reject contradictions as invalid completion. The operation layer validates contract/version and review correlation, keeps uncertainty sticky, and releases refusal details only for registered, no-effect refusal cases. These are concrete local checks, not a proof that every producer, persistence implementation, transport, or frontend binding is correct.

This boundary handles sensitive data: ledger transaction fields, CSV text, invoice source paths and digest, supplier and invoice identifiers, review DTOs, profile identifiers, and potentially tax-return or authority evidence. The CLI builds typed payloads but does not itself encrypt or persist them; its security depends on the runtime frontend/worker contract. Source-path canonicalization and file-byte handling are delegated to intake/ingestion workers after the CLI supplies a working directory or path. There is no local evidence in this chunk that every read projection is redacted, that remote captures are fresh, or that file access is constrained to an allowed root. Those require following the operation handlers, storage adapters, and provider clients. The explicit privacy handling visible here is generic invalid-frame conversion for bad bulk-CSV requests and narrowly gated release of declared refusal messages.

## Assessment and follow-up

The adapters are unusually careful about effect receipts, exact profile binding, payload identity, review versioning, and preserving unknown outcomes after submission. That design reduces the risk of a CLI claiming success from a plausible but uncorrelated result. The main unresolved risks are architectural rather than confirmed defects in these bridges: workers determine calculation correctness, authorization beyond profile matching, path and network policy, persistence and concurrency semantics, privacy redaction, and the trustworthiness/freshness of imported authority evidence. Prefix matching is intentionally used for several transaction identifiers, so synthesis should verify the domain’s CLI ID-prefix rule and collision behavior rather than treating these correlations as exact-ID checks. Review read flows and diagnostics also merit end-to-end redaction tracing. No tests are present in these assigned source slices, and no runtime checks were performed.

For synthesis, trace `run_registered_operation` into runtime contract admission, operation execution, result storage, and review services; trace ledger add/classify/allocate and evidence operations into their application handlers and persistence events; and trace filing/IVA capture into provider clients and snapshot storage. Confirm whether local-file workers enforce canonical-root, symlink, size, and content checks, and whether logs and error surfaces can contain taxpayer or invoice data. Determine the source and freshness guarantees for captured authority data, and verify that local read results stay bound to the selected profile under concurrent profile changes.

## Complete assigned-file coverage

The following 41 assigned modules were fully read at their manifest-specified line ranges:

- `period_parsing.py` (`src/cadrumo/entrypoints/cli/period_parsing.py`)
- `registered_operation_admission.py` (`src/cadrumo/entrypoints/cli/registered_operation_admission.py`)
- `registered_operation_completion.py` (`src/cadrumo/entrypoints/cli/registered_operation_completion.py`)
- `registered_operation_contracts.py` (`src/cadrumo/entrypoints/cli/registered_operation_contracts.py`)
- `registered_operation_deadlines.py` (`src/cadrumo/entrypoints/cli/registered_operation_deadlines.py`)
- `registered_operation_errors.py` (`src/cadrumo/entrypoints/cli/registered_operation_errors.py`)
- `registered_operation_exchange.py` (`src/cadrumo/entrypoints/cli/registered_operation_exchange.py`)
- `registered_operation_observations.py` (`src/cadrumo/entrypoints/cli/registered_operation_observations.py`)
- `registered_operation_projections.py` (`src/cadrumo/entrypoints/cli/registered_operation_projections.py`)
- `registered_operation_responses.py` (`src/cadrumo/entrypoints/cli/registered_operation_responses.py`)
- `registered_operation_reviews.py` (`src/cadrumo/entrypoints/cli/registered_operation_reviews.py`)
- `runtime_collab_recipient.py` (`src/cadrumo/entrypoints/cli/runtime_collab_recipient.py`)
- `runtime_counterparty.py` (`src/cadrumo/entrypoints/cli/runtime_counterparty.py`)
- `runtime_diagnostics.py` (`src/cadrumo/entrypoints/cli/runtime_diagnostics.py`)
- `runtime_expedientes_capture.py` (`src/cadrumo/entrypoints/cli/runtime_expedientes_capture.py`)
- `runtime_expedientes_read.py` (`src/cadrumo/entrypoints/cli/runtime_expedientes_read.py`)
- `runtime_filed_bulk.py` (`src/cadrumo/entrypoints/cli/runtime_filed_bulk.py`)
- `runtime_filed_history.py` (`src/cadrumo/entrypoints/cli/runtime_filed_history.py`)
- `runtime_filed_projection.py` (`src/cadrumo/entrypoints/cli/runtime_filed_projection.py`)
- `runtime_filed_read.py` (`src/cadrumo/entrypoints/cli/runtime_filed_read.py`)
- `runtime_filed_single.py` (`src/cadrumo/entrypoints/cli/runtime_filed_single.py`)
- `runtime_filed_source.py` (`src/cadrumo/entrypoints/cli/runtime_filed_source.py`)
- `runtime_invoice_catalogue.py` (`src/cadrumo/entrypoints/cli/runtime_invoice_catalogue.py`)
- `runtime_invoice_intake.py` (`src/cadrumo/entrypoints/cli/runtime_invoice_intake.py`)
- `runtime_iva_history_capture.py` (`src/cadrumo/entrypoints/cli/runtime_iva_history_capture.py`)
- `runtime_iva_remote_state_capture.py` (`src/cadrumo/entrypoints/cli/runtime_iva_remote_state_capture.py`)
- `runtime_iva_wallet_capture.py` (`src/cadrumo/entrypoints/cli/runtime_iva_wallet_capture.py`)
- `runtime_iva_wallet_history.py` (`src/cadrumo/entrypoints/cli/runtime_iva_wallet_history.py`)
- `runtime_justificante_capture.py` (`src/cadrumo/entrypoints/cli/runtime_justificante_capture.py`)
- `runtime_justificante_read.py` (`src/cadrumo/entrypoints/cli/runtime_justificante_read.py`)
- `runtime_ledger_actividad_asset.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_actividad_asset.py`)
- `runtime_ledger_add.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_add.py`)
- `runtime_ledger_allocate.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_allocate.py`)
- `runtime_ledger_attachment.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_attachment.py`)
- `runtime_ledger_bienes_inversion.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_bienes_inversion.py`)
- `runtime_ledger_bulk_classify.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_bulk_classify.py`)
- `runtime_ledger_check.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_check.py`)
- `runtime_ledger_classify.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_classify.py`)
- `runtime_ledger_evidence_add.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_add.py`)
- `runtime_ledger_evidence_followup.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_followup.py`)
- `runtime_ledger_evidence_ingestion.py` (`src/cadrumo/entrypoints/cli/runtime_ledger_evidence_ingestion.py`)
<!-- /preserved:article -->
