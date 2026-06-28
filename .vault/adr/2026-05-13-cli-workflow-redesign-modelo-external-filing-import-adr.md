---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-filing-record-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-complementaria-external-filing-path-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---
# `cli-workflow-redesign` adr: `modelo external filing import` | (**status:** `accepted`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

## Problem Statement

The complementaria external-filing-path ADR mandates that an amendment can only run when the operator has imported AEAT-attested evidence as the baseline. The amend domain (calculation-revision amendment-kind field plus filing-record amends-link) and the gate (`AmendmentEvidenceMissingError` when `external_evidence` is `None`) landed with the modelo-amend wave, but the *import path* — the production surface that populates `FilingRecord.external_evidence` — was undefined. Without an import service the amend wave can only be exercised by hand-constructing `FilingRecord` objects in tests; operators have no production path.

## Considerations

- AEAT exposes three legitimate sources of attested baseline evidence for a return the operator did not compute locally: `aeat_justificante_pdf` (the official receipt PDF downloaded after a manual filing made through Sede or a gestor), `aeat_csv_register` (the operator-visible CSV register of past filings), and `aeat_live_capture` (a read-only AEAT live snapshot captured by the existing live-read stack).
- All three carry an evidence reference id (justificante number, CSV row id, live-capture id) that downstream auditors can replay.
- The amend ADR requires the baseline filing record to be CURRENT for its (bucket, modelo, year, period) tuple. The import path must enforce the same single-current invariant: a second import for the same tuple supersedes the prior current via the existing supersession chain.
- The bucket-event-history ADR's per-service emission scope reserves `modelo.filing.imported` for this surface. The emission lands here.
- The import path is its own UX entry point under `aeat app modelo filing-record import`; placing it on the filing-record subapp (not on work) keeps the verb close to its product, which is a filing record, not a fresh work unit.

## Constraints

- No live submit. The import path is read-only against AEAT — it captures what AEAT already has, never adds to it.
- No partial imports. A casilla-value mapping with zero entries is refused (`ExternalFilingImportError`) because the import does not represent a real receipt.
- No empty evidence references. The reference id must be a non-empty string; an empty or whitespace-only string is refused. The reference is the audit-replay key.
- The imported revision lands directly in FILED state with `verified_at = filed_at = imported_at` and `verified_by = filed_by = actor`. The verify path does not run: AEAT already attested the values, so the operator did not produce them locally and the registry verifier (which checks required-manual-input casillas) does not apply.
- The imported filing record has `aeat_accepted = True` (by definition: AEAT issued the evidence) and `external_evidence` populated. No locally-computed filing record may ever set `external_evidence`; the amend path's gate depends on this invariant.
- The action emits a single `modelo.filing.imported` bucket event per call. Re-imports with identical content collapse to the same event id via the bucket-event content-addressing.

## Implementation

```text
aeat app modelo filing-record import WORK_UNIT_ID \
    --evidence-kind aeat_justificante_pdf \
    --evidence-id JUST-2026-303-Q1-... \
    --set CASILLA=VALUE [--set ...] \
    [--by ACTOR]
```

The action `import_external_filing_evidence` validates inputs (non-empty casilla values, non-empty evidence reference, work unit exists and is not discarded); builds a fresh `CalculationRevision` in FILED state with the imported casilla values and empty inputs/overrides; builds a `FilingRecord` in CURRENT status with `external_evidence` populated and `aeat_accepted=True`; supersedes any prior CURRENT filing for the tuple; advances the work-unit pointers; and emits a `MODELO_FILING_IMPORTED` bucket event referencing the new filing record id and the evidence kind plus reference id.

The CLI verb threads the operator flags into the action and renders the result through `_emit` with `filing_disambiguation = "(imported AEAT-attested baseline)"` so the operator can never confuse an import for a live submission.

## Rationale

The import path is the production source of `FilingRecord.external_evidence`. Without it the amend ADR cannot operate end-to-end: the evidence gate cannot be satisfied. Placing the action in the modelo lifecycle namespace (not in a separate filing root) keeps it inside the boundary already established by the modelo work-unit / calculation-revision / filing-record / verification-report cluster, so the supersession chain, work-unit pointer advance, and bucket-event emission all reuse the existing canonical paths instead of forking.

The verify path is intentionally skipped: AEAT already validated the return when it accepted it. Running the registry verifier over the imported values would either rubber-stamp them (no operational value) or invent a false-positive blocker against AEAT's own attestation.

## Consequences

- The amend path now has a real production source for its baseline. The four amend tests that previously constructed `FilingRecord` objects directly can be expressed end-to-end as import → amend, and the round-trip is proven by the `test_import_then_amend_unlocks_amendment_path` test.
- A second import for the same (bucket, modelo, year, period) tuple supersedes the prior current. This is the same chain file and amend use; operators can re-import without manual cleanup.
- The future justificante-PDF reader, AEAT CSV register importer, and AEAT live-capture stacks all land on this action as their persistence boundary. They produce (casilla_values, evidence_kind, evidence_reference_id) triples; the action persists them.
- `modelo.filing.imported` is now part of the closed bucket-event-history enum. The `aeat config bucket history` verb surfaces it alongside calculation / verify / file / amend events for a chronological audit view of every material modelo lifecycle transition in a bucket.
