---
tags:
  - '#exec'
  - '#component-on-demand'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:fb952dfd5b9344033fa1b90f99a3507d5deaae5b52e3f64850d73129336b1b1e'
related:
  - "[[2026-10-24-component-on-demand-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `component-on-demand` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `M` `src/cadrumo/application/provisioning_contracts.py`
- `S01` `M` `src/cadrumo/application/local_reader.py`
- `S01` `M` `src/cadrumo/application/tests/test_local_reader.py`
- `S01` `verify:` `pytest local_reader, provisioning, llm reader, batch ingest and evidence CLI suites (144)` -> `pass`
- `S01` `verify:` `ruff check/format, ty, lint-imports` -> `pass`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/factory.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_browser_provisioning_refusal.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_terminal_preconditions.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_working_data.py`
- `S04` `M` `src/cadrumo/adapters/persistence/operations/tests/test_auth_operation_definitions.py`
- `S04` `M` `src/cadrumo/application/auth/operation_definitions.py`
- `S04` `M` `src/cadrumo/application/auth/protocols.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_operation_definitions.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_passphrase_operation_access.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_provider_configure_operation_access.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_session_acquire_operation_access.py`
- `S04` `M` `src/cadrumo/entrypoints/live_state_composition.py`
- `S04` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S04` `A` `src/cadrumo/entrypoints/tests/test_live_browser_readiness_refusal.py`
- `S04` `verify:` `focused browser readiness pytest (10)` -> `pass`
- `S04` `verify:` `browser, auth, preflight, runtime auth, provisioning_browser pytest (151 passed; 2 live-only test_live_evasion need CADRUMO_LIVE_TESTS_ENABLED)` -> `pass`
- `S04` `verify:` `live operation caller pytest (128)` -> `pass`
- `S04` `verify:` `ruff check/format, ty` -> `pass`
- `S03` `M` `src/cadrumo/adapters/inbound/financial/ledger_import.py`
- `S03` `M` `src/cadrumo/adapters/inbound/financial/providers/_mapped_tabular.py`
- `S03` `M` `src/cadrumo/adapters/inbound/financial/providers/base.py`
- `S03` `M` `src/cadrumo/adapters/inbound/financial/providers/detection.py`
- `S03` `M` `src/cadrumo/adapters/inbound/financial/providers/tests/test_mapped_tabular_fallback.py`
- `S03` `A` `src/cadrumo/adapters/inbound/financial/providers/tests/test_mapped_tabular_reader_unavailable.py`
- `S03` `A` `src/cadrumo/adapters/inbound/financial/tests/test_column_reader_unavailable_import.py`
- `S03` `M` `src/cadrumo/adapters/outbound/llm/column_role_mapping.py`
- `S03` `M` `src/cadrumo/adapters/outbound/llm/supply_nature_proposal.py`
- `S03` `A` `src/cadrumo/adapters/outbound/llm/tests/test_role_reader_unavailable_is_reported.py`
- `S03` `M` `src/cadrumo/application/ledger/actions_import.py`
- `S03` `M` `src/cadrumo/application/ledger/column_roles.py`
- `S03` `M` `src/cadrumo/application/ledger/import_ports.py`
- `S03` `M` `src/cadrumo/application/ledger/protocols.py`
- `S03` `M` `src/cadrumo/core/errors/registry/_domain_part1.py`
- `S03` `M` `src/cadrumo/entrypoints/adapter_composition.py`
- `S03` `verify:` `new reader-unavailable llm/import/lane pytest (11+3+3)` -> `pass`
- `S03` `verify:` `covering callers pytest (430 passed; 1 failure from another session's uncommitted LocalStatementReader)` -> `pass`
- `S03` `verify:` `ruff, ty, pyrefly, basedpyright, lint-imports, check-operation-contract-manifest` -> `pass`
- `S02` `M` `src/cadrumo/_data/operations/contract_manifest.json`
- `S02` `M` `src/cadrumo/application/ledger/invoice_draft_extraction.py`
- `S02` `M` `src/cadrumo/application/ledger/invoice_draft_extraction_ports.py`
- `S02` `M` `src/cadrumo/application/ledger/invoice_draft_payloads.py`
- `S02` `M` `src/cadrumo/application/ledger/invoice_draft_records.py`
- `S02` `M` `src/cadrumo/application/ledger/invoice_evidence_operation_dtos.py`
- `S02` `M` `src/cadrumo/application/ledger/tests/test_evidence_followup_operation.py`
- `S02` `M` `src/cadrumo/application/ledger/tests/test_invoice_evidence_operation_dtos.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/ledger_evidence_batch_results.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_batch_cli.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_llm_vision_classifier.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_llm_vision_evidence.py`
- `S02` `M` `src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py`
- `S02` `M` `src/cadrumo/entrypoints/ledger_llm_composition.py`
- `S02` `A` `src/cadrumo/entrypoints/tests/test_evidence_reader_precheck.py`
- `S02` `M` `src/cadrumo/tests/llm_vision_evidence_support.py`
- `S02` `verify:` `extraction, classification, batch, label-reader, DTO, CLI, TUI and runtime-host pytest (474)` -> `pass`
- `S02` `verify:` `runtime host ledger suites (202)` -> `pass`
- `S02` `verify:` `pre-check removed: new tests fail (mutation check)` -> `pass`
- `S02` `verify:` `ruff, ty, lint-imports` -> `pass`
- `S06` `A` `src/cadrumo/entrypoints/cli/_component_setup_rendering.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/config/status_rendering.py`
- `S06` `M` `src/cadrumo/entrypoints/cli/errors.py`
- `S06` `A` `src/cadrumo/entrypoints/cli/tests/test_component_setup_refusal_text.py`
- `S06` `verify:` `new CLI component setup refusal text pytest (6)` -> `pass`
- `S06` `verify:` `pytest src/cadrumo/entrypoints/cli (2859)` -> `pass`
- `S06` `verify:` `ruff, ty, lint-imports` -> `pass`
- `S07` `M` `src/cadrumo/entrypoints/tui/app.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/operations/modal.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/operations/refusal_explanation.py`
- `S07` `A` `src/cadrumo/entrypoints/tui/operations/tests/test_modal_setup_offer.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/setup/destination.py`
- `S07` `A` `src/cadrumo/entrypoints/tui/setup/focus.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/setup/screen.py`
- `S07` `M` `src/cadrumo/entrypoints/tui/setup/tests/test_setup_screen.py`
- `S07` `verify:` `tui operations, setup, app and navigation unit pytest (81)` -> `pass`
- `S07` `verify:` `ruff, ty, lint-imports` -> `pass`
- `S08` `M` `native/desktop/frontend/src/App.tsx`
- `S08` `M` `native/desktop/frontend/src/components/ledger/documents/DocumentPanels.tsx`
- `S08` `M` `native/desktop/frontend/src/components/ledger/documents/DraftReview.tsx`
- `S08` `A` `native/desktop/frontend/src/components/setup/SetupOffer.stories.tsx`
- `S08` `A` `native/desktop/frontend/src/components/setup/SetupOffer.tsx`
- `S08` `M` `native/desktop/frontend/src/dev/ledgerEvidenceFixture.ts`
- `S08` `M` `native/desktop/frontend/src/dev/ledgerFixture.ts`
- `S08` `M` `native/desktop/frontend/src/shell/ledger.ts`
- `S08` `A` `native/desktop/frontend/src/shell/provisioningRecovery.ts`
- `S08` `A` `native/desktop/frontend/tests/provisioning-recovery.spec.ts`
- `S08` `A` `native/desktop/frontend/tests/scenarios/ledger-provisioning.spec.ts`
- `S08` `verify:` `npm run check (tsc, eslint, prettier)` -> `pass`
- `S08` `verify:` `provisioning-recovery unit spec (4), ledger-provisioning scenarios (5), setup/ledger-documents/ledger-matching specs (43)` -> `pass`
- `S08` `verify:` `full npm run test: 1142 passed, 22 failed from other in-flight work (rail Declarations item, panel log badge, TUI cover, window close)` -> `fail`
- `S10` `M` `src/cadrumo/adapters/outbound/llm/column_role_mapping.py`
- `S10` `M` `src/cadrumo/adapters/outbound/llm/tests/test_role_reader_unavailable_is_reported.py`
- `S10` `M` `src/cadrumo/application/invoices/_bulk_import_columns.py`
- `S10` `M` `src/cadrumo/application/invoices/bulk_import.py`
- `S10` `M` `src/cadrumo/application/invoices/catalogue_intake_operation_ports.py`
- `S10` `M` `src/cadrumo/application/invoices/tests/test_catalogue_intake_operation.py`
- `S10` `M` `src/cadrumo/application/local_reader.py`
- `S10` `M` `src/cadrumo/entrypoints/invoice_intake_operation_composition.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/test_invoice_intake_operation_composition.py`
- `S10` `verify:` `focused unit and integration pytest over 26 files (1308)` -> `pass`
- `S10` `verify:` `ruff, ty, lint-imports, check-operation-contract-manifest` -> `pass`
- `S05` `M` `src/cadrumo/adapters/inbound/financial/providers/_mapped_tabular.py`
- `S05` `M` `src/cadrumo/adapters/inbound/financial/providers/tests/test_mapped_tabular_reader_unavailable.py`
- `S05` `M` `src/cadrumo/adapters/outbound/aeat/browser/errors.py`
- `S05` `M` `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `S05` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_browser_provisioning_refusal.py`
- `S05` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_terminal_preconditions.py`
- `S05` `M` `src/cadrumo/adapters/persistence/operations/tests/test_auth_operation_definitions.py`
- `S05` `M` `src/cadrumo/application/dependency_wording.py`
- `S05` `M` `src/cadrumo/application/invoices/bulk_import.py`
- `S05` `A` `src/cadrumo/application/invoices/tests/test_bulk_import_reader_reason.py`
- `S05` `M` `src/cadrumo/application/ledger/evidence_errors.py`
- `S05` `M` `src/cadrumo/application/ledger/invoice_draft_extraction.py`
- `S05` `A` `src/cadrumo/application/ledger/tests/test_evidence_reader_refusal_key.py`
- `S05` `A` `src/cadrumo/application/tests/test_component_refusal_wording.py`
- `S05` `M` `src/cadrumo/core/errors/registry/_adapters_part1.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/_evidence_field_notices.py`
- `S05` `M` `src/cadrumo/entrypoints/cli/tests/test_evidence_field_notices.py`
- `S05` `M` `src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py`
- `S05` `M` `src/cadrumo/entrypoints/ledger_llm_composition.py`
- `S05` `M` `src/cadrumo/entrypoints/tests/test_live_browser_readiness_refusal.py`
- `S05` `M` `src/cadrumo/locales/ca/adapters.yml`
- `S05` `M` `src/cadrumo/locales/ca/application.yml`
- `S05` `M` `src/cadrumo/locales/ca/errors.yml`
- `S05` `M` `src/cadrumo/locales/en/adapters.yml`
- `S05` `M` `src/cadrumo/locales/en/application.yml`
- `S05` `M` `src/cadrumo/locales/en/errors.yml`
- `S05` `M` `src/cadrumo/locales/es/adapters.yml`
- `S05` `M` `src/cadrumo/locales/es/application.yml`
- `S05` `M` `src/cadrumo/locales/es/errors.yml`
- `S05` `M` `src/cadrumo/locales/hu/adapters.yml`
- `S05` `M` `src/cadrumo/locales/hu/application.yml`
- `S05` `M` `src/cadrumo/locales/hu/errors.yml`
- `S05` `verify:` `focused pytest (652)` -> `pass`
- `S05` `verify:` `ruff, ty, lint-imports, check-operation-contract-manifest` -> `pass`
- `S05` `verify:` `just check-locales: pre-existing failures unchanged, no new findings from S05 keys` -> `fail`

## Notes

- `S04` Start checks sit in entrypoint preflight bindings and an auth port, not under application/live, because application may not import the adapter's BrowserError; the refusal settles FAILED `(FAIL_BROWSER_SESSION_BROWSER)` until S05 adds a REFUSED code
- `S03` Supply-nature proposals have no production caller, so their `reader_unavailable` verdict reaches no operation result yet; invoice bulk intake's silent decline moves to S10; the mapping refusal reason is an English adapter sentence until S05 words it
- `S02` Pre-checks sit in the reader wiring (entrypoints) so injected test readers stay unaffected; the label fallback stays a success and now carries `recovery_action_id;` batch ingest unchanged
- `S06` Helper lives in the new `_component_setup_rendering.py` because `_action_rendering.py` is gated to its one serializer; browser refusal context lines (failure mode) still print until S05
- `S07` Offer lives in the operation modal and app root (outside the row) because the modal closes on settlement; label composes the existing set-up key with the item name; integration failures seen were in the production registry build from other uncommitted work
- `S08` Readers projections carry no recovery action id, so the Readers tab offers setup when the local AI row is set-up-able; Modelo and Censo ports carry no verdict and are not routed
- `S10` Mapping model resolves through `select_role_model` for both probe and dispatch; `map_column_roles` removed for `resolve_header_roles;` text and vision readers still send their raw settings (out of scope)
- `S05` Missing browser now settles `REFUSED_BROWSER_NOT_READY` with a message key and no internal context lines; unused cli.yml key `cli.app.ledger.evidence.label_reading_reader_unavailable` and the TUI's own label-reading wording are left for S09 cleanup
