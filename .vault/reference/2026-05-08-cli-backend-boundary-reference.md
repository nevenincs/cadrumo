---
tags:
  - '#reference'
  - '#cli-backend-boundary'
date: '2026-05-08'
modified: '2026-05-08'
related: []
---



# `cli-backend-boundary` reference: `cli-backend-boundary-reference`

This reference records the current CLI/backend boundary violations identified
from the Python CLI implementation, adjacent CLI tests, import-contract CLI
tests, and existing backend services. It is the source inventory for the
implementation plan.

The boundary is strict. CLI code may bind Typer commands, accept options,
construct application-layer command inputs, render returned DTOs, and translate
backend errors. Business rules, persistence decisions, parsing grammars,
calculations, workflow orchestration, and cross-domain state changes must live
in the application layer or domain services.

## Status Taxonomy

| Status | Meaning |
|---|---|
| `pending` | Confirmed issue or task not yet started. |
| `in-progress` | Active remediation is underway. |
| `done` | Migrated, reviewed, and verified. |
| `blocked` | Cannot proceed due to missing required information or dependency. |
| `deferred-for-backend-gap` | CLI behavior cannot move cleanly until an application-layer or domain API exists. |

## Issue Inventory

| Row | Status | Taxonomy | Severity | Evidence anchors | Boundary issue |
|---|---|---:|---|---|---|
| CLI-001 | pending | CLI-BL-PARSE | High | `src/aeat/entrypoints/cli/_common.py::_canonical_period`, `src/aeat/entrypoints/cli/_common.py::_profile_to_autonomo`, `src/aeat/entrypoints/cli/_common.py::_aggregate_filing_inputs` | CLI owns period grammar, setup profile to `AutonomoProfile` defaulting, and filing input aggregation stub behavior. |
| CLI-002 | deferred-for-backend-gap | CLI-BL-ORCH | High | `src/aeat/entrypoints/cli/_ledger.py::ledger_import`, `src/aeat/entrypoints/cli/_ledger.py::_direction_resolver`, `src/aeat/entrypoints/cli/_ledger.py::ledger_review`, `src/aeat/entrypoints/cli/_ledger.py::ledger_edit` | CLI owns ledger provider detection, dry-run/import summaries, source digests, sign-to-direction mapping, review status derivation, and split parsing. Period filtering checks only the year prefix, so `2026Q1` can match all 2026 rows. |
| CLI-003 | backend-owned-wrapper-verification | CLI-BL-ORCH | High | `src/aeat/entrypoints/cli/_invoice.py::invoice_import`, `src/aeat/entrypoints/cli/_invoice.py::invoice_review` | Invoice import parsing, defaults, line synthesis, duplicate handling, import summaries, review projections, IVA display totals, status, and payment matching now live in `application.invoices`; the CLI wrapper renders backend DTOs. |
| CLI-004 | deferred-for-backend-gap | CLI-BL-PARSE | High | `src/aeat/entrypoints/cli/financial/profile.py`, `src/aeat/entrypoints/cli/financial/_profile_aliases.py::_resolve_key`, `src/aeat/entrypoints/cli/financial/_profile_aliases.py::FAMILY_ALIASES` | CLI owns usage-ratio alias families, eligible-key resolution, suggestions, ratio parsing, and usage-ratio profile load/save semantics. |
| CLI-005 | deferred-for-backend-gap | CLI-BL-ORCH | High | `src/aeat/entrypoints/cli/financial/txs.py::classify_cmd`, `src/aeat/entrypoints/cli/financial/txs.py::classify_llm_cmd`, `src/aeat/entrypoints/cli/financial/txs.py::_resolve_effective_pct`, `src/aeat/entrypoints/cli/financial/txs.py::_build_catalogue` | CLI owns transaction target selection, percentage defaults, confidence parsing, LLM retry states, reason composition, NDJSON/provider catalogue import, and encoding fallback. |
| CLI-006 | backend-owned-wrapper-verification | CLI-BL-STATE | High | `src/aeat/entrypoints/cli/financial/invoices.py::reconcile_cmd`, `src/aeat/entrypoints/cli/financial/invoices.py::link_cmd` | `reconcile --apply` and `link` now delegate mutation and persistence to `application.invoices`; the CLI renders backend DTOs and translated errors only. |
| CLI-007 | deferred-for-backend-gap | CLI-BL-CALC | Critical | `src/aeat/entrypoints/cli/filing/__init__.py::_load_inputs`, `src/aeat/entrypoints/cli/filing/__init__.py::build`, `src/aeat/entrypoints/cli/filing/__init__.py::_handle_declaracion_import`, `src/aeat/entrypoints/cli/_declaration.py::declaration_edit` | CLI coerces numeric filing inputs, manages filing draft repositories and pointers, imports declaracion through an adapter directly, hard-rejects borrador, and rebuilds/saves edited declaration drafts. |
| CLI-008 | deferred-for-backend-gap | CLI-BL-QUERY | Medium | `src/aeat/entrypoints/cli/_overview.py::overview_status`, `src/aeat/entrypoints/cli/deadlines/_helpers.py::load_profile`, `src/aeat/entrypoints/cli/deadlines/next.py` | CLI combines repository counts, period draft filters, profile loading, deadline engine construction, and import-time default year. |
| CLI-009 | deferred-for-backend-gap | CLI-BL-CALC | Critical | `src/aeat/entrypoints/cli/registry.py::inspect_registry_tree`, `src/aeat/entrypoints/cli/registry.py::select_declarations_for_capture`, `src/aeat/entrypoints/cli/registry.py::_filing_period_date`, `src/aeat/entrypoints/cli/registry.py::verify_filed_state` | CLI owns registry report DTOs, registry tree audits, filed-data selectors, AEAT capture orchestration, period-date mapping, local-vs-observed filed-state verification, and oracle audit plumbing. |
| CLI-010 | pending | CLI-BL-CALC | Critical | `src/aeat/entrypoints/cli/data/ledgers/inventory.py::create_inventory`, `src/aeat/entrypoints/cli/data/ledgers/inventory.py::add_movement`, `src/aeat/entrypoints/cli/data/ledgers/inventory.py::_money` | CLI constructs domain inventory ledgers and movements, parses dates/money, and talks to persistence adapters directly. |
| TEST-001 | pending | TEST-FP-OUTPUT | Low | `src/aeat/entrypoints/cli/deadlines/test_cli.py` | Tests rely mostly on substring/output assertions and curated process state for environment/default-profile behavior. |
| TEST-002 | pending | TEST-FP-META | Medium | `src/aeat/entrypoints/cli/financial/test_profile.py`, `src/aeat/entrypoints/cli/financial/test_profile_aliases.py` | Tests pin CLI-owned alias, suggestion, wrapping, parsing, and persistence behavior that should move behind an application API. |
| TEST-003 | pending | TEST-TAUTO-CALC | Critical | `src/aeat/entrypoints/cli/data/ledgers/test_data_ledgers_cli.py` | CLI-level inventory tests assert hand-derived COGS and closing stock; calculation contracts need backend relocation and external-authority review. |
| TEST-004 | pending | TEST-TAUTO-CALC | Critical | `src/aeat/entrypoints/cli/test_registry_cli.py` | Tests cover registry inventory, filed-state comparison, selectors, and workbook parity through CLI DTOs; synthetic calculation assertions require backend relocation and no-tautology review. |
| TEST-005 | pending | TEST-FP-META | Medium | `tests/import_contract/domain/transactions/test_cli.py` | Tests pin CLI transaction filtering, manual classification, LLM orchestration, confidence parsing, encoding fallback, and provider building, including scripted providers/test seams. |
| TEST-006 | backend-owned-wrapper-verification | TEST-FP-META | Medium | `tests/import_contract/domain/invoices/test_cli.py`, `src/aeat/application/invoices/test_linking.py`, `src/aeat/application/invoices/test_queries.py`, `src/aeat/application/invoices/test_reconciliation.py` | Invoice CLI import-contract tests now cover wrapper rendering and exit translation only. Query, link, consistency, unmatched, and reconciliation behavior are covered at the application layer. |
| TEST-007 | pending | TEST-FP-OUTPUT | Medium | `src/aeat/entrypoints/cli/test_user_cli_surface.py` | End-to-end flows assert process success or file absence without validating business values, creating false-positive coverage. |
| TEST-008 | pending | TEST-FP-META | Low | `src/aeat/entrypoints/cli/browser/test_health.py` | Fake probe seams are acceptable only as CLI rendering tests, not as proof of backend health behavior. |
| API-001 | deferred-for-backend-gap | API-GAP | High | `src/aeat/application/transactions/_import.py::import_ledger_with_diagnostics` | Ledger import needs an application workflow for provider resolution, validation, dry-run/persist result, diagnostics, digest, and repository merge. |
| API-002 | deferred-for-backend-gap | API-GAP | High | `src/aeat/domain/transactions/_service.py::set_classification`, `src/aeat/domain/transactions/_models.py` | Transaction classification needs an application workflow for target selection, percentage defaults, confidence parsing, reason merge, LLM retry state, and save semantics. |
| API-003 | backend-owned-wrapper-verification | API-GAP | High | `src/aeat/application/invoices`, `src/aeat/domain/invoices/_service.py` | Invoice import, review/match projections, list/show/unmatched/verify queries, explicit bidirectional link commands, and reconciliation apply persistence are now application services. |
| API-004 | deferred-for-backend-gap | API-GAP | High | `src/aeat/domain/usage_ratios/_model.py::UsageRatioProfile`, `src/aeat/domain/usage_ratios/_service.py::load_usage_ratios`, `src/aeat/application/profile/__init__.py` | Usage-ratio commands need an application service for alias resolution, suggestions, parse diagnostics, and atomic profile load/save. |
| API-005 | deferred-for-backend-gap | API-GAP | Critical | `src/aeat/application/filing/_calculate.py::summarise_calculation`, `src/aeat/application/filing/runtime.py` | Filing and declaration need aggregate-input and workflow services for edit, approve, validate, export, import, filed-state verification, and user-cli pointer updates. |
| API-006 | deferred-for-backend-gap | API-GAP | Critical | `src/aeat/domain/calculations/registry/__init__.py` | Registry needs application services for tree reports, filed-data listing, filed-state verification, period-date mapping, capture orchestration, and oracle audit plumbing. |
| API-007 | deferred-for-backend-gap | API-GAP | Critical | `src/aeat/domain/profile/inventory/__init__.py` | Inventory needs an application service for create/add/preview DTOs, parser boundaries, and repository abstraction. |
| API-008 | deferred-for-backend-gap | API-GAP | Medium | `src/aeat/domain/deadlines/_engine.py::DeadlineEngine`, `src/aeat/application/overview/__init__.py::build_overview_calendar` | Overview and deadlines need facades for injectable clock, configured-profile loading, and status aggregation. |

## Existing Backend Anchors

Use existing backend contracts where possible: `import_ledger_with_diagnostics`,
`set_classification`, transaction model validation,
`src/aeat/application/invoices/__init__.py`,
`src/aeat/domain/invoices/_service.py`, `summarise_calculation`,
`src/aeat/application/filing/runtime.py`, filing export/import/reconciliation
services, `UsageRatioProfile`, `load_usage_ratios`, profile listing/validation
in `src/aeat/application/profile/__init__.py`, `DeadlineEngine`,
`build_overview_calendar`, registry public API in
`src/aeat/domain/calculations/registry/__init__.py`, and inventory domain
functions in `src/aeat/domain/profile/inventory/__init__.py`.
