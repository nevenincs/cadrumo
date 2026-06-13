---
tags:
  - '#plan'
  - '#cli-backend-boundary'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-cli-backend-boundary-adr]]"
  - "[[2026-05-08-cli-backend-boundary-reference]]"
  - "[[2026-05-08-cli-backend-boundary-research]]"
---



# `cli-backend-boundary` `rollout` plan

This plan makes CLI/backend boundary enforcement executable. The CLI is not an
application layer. It must become a wrapper around backend command services and
domain APIs. Every row from the reference inventory remains trackable until it
is migrated, reviewed, and verified.

## Proposed Changes

The implementation will remove business logic from CLI modules and move missing
behavior into backend application services. CLI tests will be reduced to command
wiring, option parsing, rendering, and error translation. Backend tests will own
business behavior, persistence semantics, parsing contracts, calculations,
state transitions, and import/export round trips.

The plan is grounded in `2026-05-08-cli-backend-boundary-reference` and
`2026-05-08-cli-backend-boundary-research`.

## Tasks


## Backend Owner Matrix

| Row | Owner | Backend gap | Status |
|---|---|---|---|
| CLI-001 | `application.filing` | API-005 | tracked-current-violation |
| CLI-002 | `application.transactions` | API-001 | tracked-current-violation |
| CLI-003 | `application.invoices` | API-003 | backend-owned-wrapper-verification |
| CLI-004 | `application.profile` | API-004 | tracked-current-violation |
| CLI-005 | `application.transactions` | API-002 | tracked-current-violation |
| CLI-006 | `application.invoices` | API-003 | backend-owned-wrapper-verification |
| CLI-007 | `application.filing` | API-005 | tracked-current-violation |
| CLI-008 | `application.overview` | API-008 | tracked-current-violation |
| CLI-009 | `application.registry` | API-006 | tracked-current-violation |
| CLI-010 | `application.inventory` | API-007 | tracked-current-violation |

## Wave 0: Contract Freeze And Audit Harness

| Task | Status | Tracks | Work |
|---|---|---|---|
| W0-T1 | completed | all rows | Define the CLI boundary contract in code-review terms: Typer binding, option parsing, rendering, and error translation only. |
| W0-T2 | pending | TEST-001 to TEST-008 | Reclassify CLI tests as rendering or error-translation tests unless they verify behavior through application-layer APIs. |
| W0-T3 | pending | TEST-003, TEST-004 | Mark calculation-contract tests for no-tautology review before migration. |
| W0-T4 | completed | API-001 to API-008 | Create row-level backend API backlog entries before changing CLI behavior. |
| W0-T5 | in-progress | all rows | Add an audit checklist that every later wave updates with row status and evidence anchors. |

Gate after Wave 0: code review verifies every tracked row has a target owner,
status, severity, and test migration path. Audit review verifies no row uses
overloaded “verify” language without a qualifier.

## Wave 1: Shared Grammar, Profile, And Parser Boundaries

| Task | Status | Tracks | Work |
|---|---|---|---|
| W1-T1 | deferred-for-backend-gap | CLI-001, API-005 | Move period canonicalization and aggregate filing input ownership behind application-layer filing services. |
| W1-T2 | deferred-for-backend-gap | CLI-004, API-004 | Move usage-ratio alias resolution, suggestions, parse diagnostics, and atomic profile save/load into an application service. |
| W1-T3 | pending | CLI-010, API-007 | Move inventory date and money parsing behind an inventory application service. |
| W1-T4 | pending | TEST-002, TEST-003 | Replace CLI-pinned parser/calculation assertions with application-layer contract tests and thin CLI rendering tests. |

Gate after Wave 1: code review confirms CLI modules no longer define domain
grammars for periods, usage ratios, inventory money, or profile aliases. Audit
review confirms setup profile, active CLI profile, `AutonomoProfile`, and
usage-ratio profile remain distinct.

## Wave 2: Ledger And Transaction Workflows

| Task | Status | Tracks | Work |
|---|---|---|---|
| W2-T1 | deferred-for-backend-gap | CLI-002, API-001 | Add ledger import workflow for provider resolution, validation, dry-run/persist result, diagnostics, digest, and repository merge. |
| W2-T2 | deferred-for-backend-gap | CLI-002 | Fix period filtering by moving period-aware filtering out of CLI and covering `YYYYQn` behavior in backend tests. |
| W2-T3 | deferred-for-backend-gap | CLI-005, API-002 | Add transaction classification workflow for manual and LLM target selection, percentage defaults, confidence parsing, retry state, reason merge, and save semantics. |
| W2-T4 | deferred-for-backend-gap | CLI-005, API-002 | Add transaction catalogue builder service for NDJSON/provider import, encoding fallback, and extension fallback. |
| W2-T5 | pending | TEST-005 | Move transaction import-contract behavior from CLI tests to backend contract tests; retain CLI tests only for command wiring, rendering, and error translation. |

Gate after Wave 2: code review confirms `src/aeat/entrypoints/cli/_ledger.py`
and `src/aeat/entrypoints/cli/financial/txs.py` do not derive
classifications, digest identity, retry state, confidence semantics, provider
behavior, or period matches. Audit review confirms no scripted provider seam is
treated as proof of service behavior.

## Wave 3: Invoice Import, Review, Link, And Reconcile

| Task | Status | Tracks | Work |
|---|---|---|---|
| W3-T1 | completed | CLI-003, API-003 | Add invoice import workflow for JSON/CSV parsing, defaults, line synthesis, duplicate handling, and import summaries. |
| W3-T2 | completed | CLI-003, API-003 | Add invoice review/match projection service for IVA display totals, payment status, period-aware matching, and overlays. |
| W3-T3 | completed | CLI-006, API-003 | Add reconciliation apply service that persists invoice and transaction catalogues atomically. |
| W3-T4 | completed | CLI-006 | Replace dummy `Path()` backend calls with explicit application-layer command inputs. |
| W3-T5 | completed | TEST-006 | Move invoice list/link/reconcile/verify/unmatched business assertions to domain or application-layer tests. |

Gate after Wave 3: code review confirms invoice CLI commands only translate
options to command DTOs and render returned projections. Audit review confirms
payment matching, IVA display recomputation, duplicate semantics, and catalogue
mutation are not CLI-owned.

## Wave 4: Filing, Declaration, Overview, And Deadlines

| Task | Status | Tracks | Work |
|---|---|---|---|
| W4-T1 | deferred-for-backend-gap | CLI-007, API-005 | Add declaration aggregate-input service to replace empty CLI aggregation. |
| W4-T2 | deferred-for-backend-gap | CLI-007, API-005 | Add filing/declaration workflow service for edit, approve, validate, export, import, filed-state verification, and user-cli pointer updates. |
| W4-T3 | deferred-for-backend-gap | CLI-008, API-008 | Add overview/deadline facades for configured-profile loading, injectable clock, status aggregation, and period draft filters. |
| W4-T4 | pending | TEST-001, TEST-007 | Replace substring-only and process-success assertions with focused CLI rendering tests plus backend behavior tests. |

Gate after Wave 4: code review confirms filing draft, declaration, local
export, justificante/declaracion import, and filed-state capture are represented
by distinct backend contracts. Audit review confirms live submission remains
out of scope.

## Wave 5: Registry And Inventory

| Task | Status | Tracks | Work |
|---|---|---|---|
| W5-T1 | deferred-for-backend-gap | CLI-009, API-006 | Add registry audit/capture service for tree reports, filed-data selectors, period-date mapping, filed-state verification, and oracle audit plumbing. |
| W5-T2 | deferred-for-backend-gap | CLI-010, API-007 | Add inventory application service for create/add/preview DTOs, parser boundaries, and repository abstraction. |
| W5-T3 | pending | TEST-004 | Move registry inventory, filed-state comparison, selector, and workbook parity contracts behind backend tests. |
| W5-T4 | pending | TEST-003 | Move inventory COGS/closing-stock contracts behind non-tautological backend tests with external-authority expectations. |

Gate after Wave 5: code review confirms registry and inventory CLI code does
not construct domain ledgers, perform comparisons, map period dates, or own
audit DTOs. Audit review confirms workbook parity verify, registry tree verify,
and filed-state verify remain separate contracts.

## Wave 6: Final CLI Thin-Wrapper Verification

| Task | Status | Tracks | Work |
|---|---|---|---|
| W6-T1 | pending | all CLI rows | Inspect CLI modules for remaining business logic categories: parse, query, state, orchestration, calculation, private imports. |
| W6-T2 | pending | all test rows | Ensure CLI tests exercise command wiring, option parsing, rendering, and error translation only. |
| W6-T3 | pending | API-001 to API-008 | Verify every displaced behavior has an application-layer or domain owner and non-tautological tests. |
| W6-T4 | pending | all rows | Update row statuses to `done`, `blocked`, or `deferred-for-backend-gap` with evidence anchors. |

Gate after Wave 6: final audit must show no `CLI-BL-CALC`, `CLI-BL-ORCH`,
`CLI-BL-STATE`, `CLI-BL-PARSE`, `CLI-BL-QUERY`, or `CLI-PRIVATE` behavior
remains in CLI modules except option parsing and error translation.

## Parallelization

Parallelization is allowed only across disjoint backend service areas with
separate write sets. Ledger/transaction, invoice, filing/declaration,
registry, and inventory can proceed in parallel after Wave 0 if each worker
owns a distinct application-layer module and matching tests. CLI module edits
must wait for their backend service owners to land or must be scoped to command
wiring only.

## Verification

A CLI command is a thin wrapper only when all criteria hold:

- The CLI accepts Typer arguments/options and converts them to application-layer
  command inputs without domain interpretation beyond command-line syntax.
- The CLI does not parse domain grammars such as `YYYYQn`, AEAT tokens like
  `1T`, month numbers, usage ratios, confidence values, money, dates, invoice
  payloads, or ledger source formats.
- The CLI does not compute tax, inventory, registry, declaration, IVA display,
  payment status, period matching, or workbook parity outcomes.
- The CLI does not mutate repositories, review state, user-cli pointers,
  invoice catalogues, transaction catalogues, filing drafts, declarations, or
  inventory ledgers directly.
- The CLI does not construct domain services from low-level pieces when an
  application-layer facade should own configuration, clock, profile loading, and
  persistence.
- The CLI does not import private application/domain/adapter internals to bypass
  public contracts.
- CLI tests assert rendering, exit status, option wiring, and error translation;
  backend tests assert business behavior.
- Calculation tests are non-tautological and do not derive expected values from
  the same formula or a synthetic mirror of the implementation.
