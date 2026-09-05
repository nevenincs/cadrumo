---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:64bcd001bf4e543a8c00effa2b37ce19f7e0f9f9392826218bd9c9f735231347'
step_id: 'S22'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the remaining unreferenced non-exported findings module by module, following each deletion cascade and lowering the ratchet rather than removing a still-populated entry

## Scope

- `src/cadrumo`

## Changes

- `M` `src/cadrumo/adapters/inbound/einvoice/shape.py`
- `M` `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_page_flow.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/_adapter_utils.py`
- `M` `src/cadrumo/adapters/persistence/profile/invoices.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/acceleration_receipt.py`
- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `M` `src/cadrumo/application/aggregation/iva_ledger.py`
- `M` `src/cadrumo/application/corpus_search/terminology.py`
- `M` `src/cadrumo/application/filing/draft_review.py`
- `M` `src/cadrumo/application/flows/review.py`
- `M` `src/cadrumo/application/invoices/catalogue_reads.py`
- `M` `src/cadrumo/application/ledger/counterparty_establishment.py`
- `M` `src/cadrumo/application/modelo/workspace_models.py`
- `M` `src/cadrumo/application/registry/source_connectivity_coverage.py`
- `M` `src/cadrumo/core/config.py`
- `M` `src/cadrumo/core/filing_projection_ref.py`
- `M` `src/cadrumo/core/orden_anual_html.py`
- `M` `src/cadrumo/core/text_fold.py`
- `M` `src/cadrumo/core/tests/test_text_fold.py`
- `M` `src/cadrumo/domain/calculations/registry/_m303_orden_projection_compiler.py`
- `M` `src/cadrumo/domain/calculations/registry/_m303_orden_source.py`
- `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `M` `src/cadrumo/domain/calculations/registry/detail_record_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design.py`
- `M` `src/cadrumo/domain/calculations/registry/record_design_pdf_state.py`
- `M` `src/cadrumo/domain/contribuyente/marriage_facts.py`
- `M` `src/cadrumo/domain/prorrata_register/register.py`
- `M` `src/cadrumo/domain/transactions/classification_rule.py`
- `M` `src/cadrumo/domain/transactions/irpf_categories.py`
- `M` `src/cadrumo/domain/user_profile/values.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live_auth_preflight.py`
- `M` `src/cadrumo/entrypoints/cli/_common.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_evidence_consent_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_review_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_support.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_aggregate_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_participation_cli.py`
- `M` `src/cadrumo/entrypoints/cli/config/_profile_support.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/audit/unreachable_code.py`
- `M` `dev/audit/tests/test_unreachable_code.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_ratchet` -> `fail`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py -m ""` -> `pass`

## Notes

The ratchet exits 1 naming three modules this Step did not touch -
`_validate_parameter_temporal`, `domain.invoices.service` and
`_app_ledger_command_specs` - each introduced by concurrent peer work or by a
cascade this Step recorded rather than resolved.

Two findings were the audit's own false positives, not code: `_AttachmentFileReader`
and `_ResponseWaiter` are named only inside `cast("X | None", ...)` strings, which
the dotted-spec reader could not resolve. The audit now reads forward references
in type positions and reports neither.

`resolve_ledger_transaction_id` was NOT deleted despite appearing unused; the
same applies to every symbol recorded in the classification ledger under
`should-be-live`, `staged-capability`, `design-time-authority` and
`deferred-by-ownership`. Deleting those would have removed capability, ports or
staged features rather than dead code.
