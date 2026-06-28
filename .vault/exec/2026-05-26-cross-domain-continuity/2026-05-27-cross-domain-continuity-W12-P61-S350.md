---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S350
date: "2026-05-27"
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-cross-domain-continuity-W12-P61-S279]]"
  - "[[2026-05-27-cross-domain-continuity-W12-P61-S280]]"
commits:
  - f45a8532c
  - 2ae2b1a10
---


# cross-domain-continuity W12.P61.S350

## What was done

Typed 13 CLI entrypoint payload/row helper functions that previously returned
`dict[str, object]` at CLI JSON boundaries. Split into two batches.

**Batch 1 — `_modelo_payloads.py`** (commit f45a8532c):

- Added `ExternalEvidencePayload` sub-model for filing-record external evidence.
- Added `legal_refs: list[str]` and `source_refs: list[str]` to `FindingPayload`
  using `Field(default_factory=list)` to satisfy RUF012.
- Added `external_evidence: ExternalEvidencePayload | None` and
  `amends_filing_record_id: str | None` to `ModeloRecordPayload`.
- Added `pydantic.Field` import.

Note: `_modelo.py` changes for S350 Batch 1 were already present in HEAD
from the concurrent W05.P26.S99 iva-wallet campaign commit `e9f45806c`.
All 5 functions (`_work_unit_payload`, `_calculation_revision_payload`,
`_result_summary_payload`, `_filing_record_payload`,
`_verification_report_payload`) return typed `OutputSchema` models and all
callers use `.model_dump(mode="python")` at spread sites. N814 alias
violations and I001 import-ordering lint issues were also already resolved
in that commit.

**Batch 2 — `_ledger.py`, `_config/__init__.py`, `_common.py`, `_app_live.py`**
(commit 2ae2b1a10):

- `_evidence_payload`: `dict[str, object]` → `Mapping[str, object]` (no caller mutation).
- `_bucket_history_event_payload`: `dict[str, object]` → `Mapping[str, object]` (no mutation).
- `_portal_row`, `_expedientes_row`, `_verify_row`, `_borrador_row`:
  `dict[str, object]` → `Mapping[str, object]` (callers subscript-read only).
- `_business_invoice_payload`: kept `dict[str, object]` with inline boundary comment
  documenting the post-call mutation pattern (callers append `bucket_event_ids`).
- `_aggregate_filing_inputs`: kept `dict[str, object]` — returns a casilla-id → Decimal
  binding dict consumed as calculation engine overrides, not a CLI JSON payload.
  Updated docstring documents the mutation contract.
- UP037 pre-existing lint fix in `_common.py` (redundant string annotation on
  `activate_subcommand_output_language`).

## Verification

- `ruff check` clean on all modified files.
- `src/aeat/entrypoints/cli/_config/` test suite: 24 passed.
- `src/aeat/entrypoints/cli/` suite (excluding pre-existing `test_audit_remediation`
  failure): running at commit time; `_config/` subset clean.

## Boundary decisions

Two functions intentionally retain `dict[str, object]` with documented rationale:

- `_business_invoice_payload`: post-call mutation (`payload["bucket_event_ids"] = ...`)
  makes `Mapping` semantically wrong; the mutation is the API contract.
- `_aggregate_filing_inputs`: not a JSON payload — it is a casilla binding dict fed
  into the calculation engine. The `dict[str, object]` typing is correct here.
