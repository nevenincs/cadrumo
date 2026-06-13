---
tags:
  - '#research'
  - '#cli-backend-boundary'
date: '2026-05-08'
modified: '2026-05-08'
related: []
---



# `cli-backend-boundary` research: `cli-backend-boundary-research`

This research establishes the implementation boundary for the AEAT CLI. The
current problem is systemic: multiple CLI modules are acting as application
services. That is not acceptable for this codebase. The application layer and
domain services must own behavior; the CLI must only expose it.

## Boundary Contract

The CLI may do the following:

- bind Typer commands and options;
- pass raw option values into application-layer command inputs;
- render returned DTOs as text, JSON, table, or other supported formats;
- translate backend exceptions into CLI exit codes and user-facing errors.

The CLI must not do the following:

- parse domain grammars such as filing periods, AEAT period tokens, invoice
  payloads, source file formats, money, usage ratios, confidence values, or
  tax-specific dates;
- compute tax, inventory, IVA display values, payment status, registry parity,
  deadline coverage, declaration values, or filing-state comparisons;
- mutate repositories, review state, filing draft pointers, invoice catalogues,
  transaction catalogues, inventory ledgers, or filed-state stores directly;
- apply cross-domain workflows such as import, match, reconcile, classify,
  approve, export, verify, or capture;
- import private application, domain, or adapter internals to bypass public
  backend contracts.

## Regression Domains

### Shared CLI Helpers

`src/aeat/entrypoints/cli/_common.py` contains shared behavior that should be
owned by the application layer. `_canonical_period` owns period grammar,
`_profile_to_autonomo` owns profile projection and defaulting, and
`_aggregate_filing_inputs` is an empty input aggregation stub. These are backend
regressions because declaration calculation cannot be reliably driven by a CLI
helper.

### Ledger

`src/aeat/entrypoints/cli/_ledger.py` owns provider resolution, validation
payloads, dry-run and persist summaries, source hashing, transaction direction
mapping, review filtering, review status derivation, split parsing, and review
state mutation. The observed period filter matches only the year prefix, so a
quarterly filter can include rows from the wrong quarter. This is both a
business-logic boundary violation and a correctness risk.

### Invoice

`src/aeat/entrypoints/cli/_invoice.py` parses invoice JSON and CSV, applies
domain defaults, synthesizes invoice lines, merges duplicates, recomputes IVA
display totals after review edits, derives invoice status, and matches invoices
to ledger rows. These behaviors need an application-layer invoice workflow.

### Financial Transactions

`src/aeat/entrypoints/cli/financial/txs.py` owns manual classification,
LLM classification, target selection, percentage defaults, confidence parsing,
retry state, reason composition, catalogue import, encoding fallback, and save
semantics. This is one of the clearest boundary violations because it makes the
CLI the financial classification application.

### Financial Profile

`src/aeat/entrypoints/cli/financial/profile.py` and
`src/aeat/entrypoints/cli/financial/_profile_aliases.py` own usage-ratio alias
families, eligible-key resolution, suggestions, parse diagnostics, and profile
load/save command semantics. These must become backend profile or usage-ratio
commands.

### Financial Invoices

`src/aeat/entrypoints/cli/financial/invoices.py` uses domain services but still
applies reconciliation suggestions, mutates two catalogues, saves both, and
passes dummy `Path()` values through link flows. The backend service boundary is
incomplete because atomic apply and command input contracts are missing.

### Filing And Declaration

`src/aeat/entrypoints/cli/filing/__init__.py` and
`src/aeat/entrypoints/cli/_declaration.py` coerce filing inputs, manage draft
repositories, manage user-cli pointers, import declaracion directly through an
adapter, reject borrador inside CLI code, and rebuild edited drafts. Filing
draft, declaration, local export, justificante/declaracion import, and
filed-state capture require separate backend workflow contracts.

### Overview And Deadlines

`src/aeat/entrypoints/cli/_overview.py` and
`src/aeat/entrypoints/cli/deadlines/**` combine repository counts, profile
loading, deadline engine construction, period draft filtering, and default
year behavior. This should be a configured application facade with injectable
clock and explicit profile source.

### Registry

`src/aeat/entrypoints/cli/registry.py` owns report DTO assembly, registry tree
audit orchestration, filed-data selectors, AEAT capture orchestration, period
date mapping, local-vs-observed filed-state verification, and oracle audit
plumbing. Registry tree verify, workbook parity verify, filed-state verify, and
export verify are separate contracts and must not be collapsed into CLI logic.

### Inventory Ledgers

`src/aeat/entrypoints/cli/data/ledgers/inventory.py` constructs inventory
ledgers and movements, parses dates and money, and calls persistence adapters
directly. Inventory create/add/preview needs an application service with DTOs
and backend-owned parser boundaries.

## Test Findings

CLI tests currently mix rendering assertions with business behavior assertions.
This creates false-positive coverage because command success, substring output,
or file absence can pass while backend behavior is absent or wrong.

Tests requiring migration include:

- `src/aeat/entrypoints/cli/deadlines/test_cli.py`, which is mostly output
  assertions and curated environment/default-profile process state;
- `src/aeat/entrypoints/cli/financial/test_profile.py` and
  `src/aeat/entrypoints/cli/financial/test_profile_aliases.py`, which pin
  CLI-owned usage-ratio behavior;
- `src/aeat/entrypoints/cli/data/ledgers/test_data_ledgers_cli.py`, which
  asserts inventory calculations through the CLI;
- `src/aeat/entrypoints/cli/test_registry_cli.py`, which tests registry
  comparison and parity behavior through CLI DTOs;
- `tests/import_contract/domain/transactions/test_cli.py`, which pins CLI
  ownership of transaction classification and provider building;
- `tests/import_contract/domain/invoices/test_cli.py`, which treats the CLI as
  owner of invoice list, link, reconcile, verify, and unmatched workflows;
- `src/aeat/entrypoints/cli/test_user_cli_surface.py`, where some end-to-end
  tests assert process success or file absence without validating business
  values;
- `src/aeat/entrypoints/cli/browser/test_health.py`, where fake probe seams are
  acceptable only as rendering tests.

## Backend API Gaps

The following backend elements must be implemented before the CLI can become a
thin wrapper:

- ledger import workflow for provider resolution, validation, dry-run/persist
  result, diagnostics, source digest, and repository merge;
- transaction classification workflow for manual and LLM flows, target
  selection, percentage defaults, confidence parsing, retry state, reason merge,
  and save semantics;
- transaction catalogue builder for NDJSON/provider source import, encoding
  fallback, and extension fallback;
- invoice import workflow for flat JSON/CSV parsing, defaults, line synthesis,
  duplicate summaries, and validation diagnostics;
- invoice review and match projection service for overlays, IVA display totals,
  payment status, and period-aware matching;
- invoice reconciliation apply service that persists invoice and transaction
  catalogues atomically;
- usage-ratio command service for alias resolution, suggestions, parse
  diagnostics, and atomic profile load/save;
- declaration aggregate-input service to replace empty CLI aggregation;
- filing/declaration workflow service for edit, approve, validate, export,
  import, filed-state verification, and user-cli pointer updates;
- registry audit/capture service for tree reports, filed-data listing,
  filed-state verification, period-date mapping, capture orchestration, and
  oracle audit plumbing;
- inventory application service for create/add/preview DTOs, parser boundaries,
  and repository abstraction;
- overview/deadline facades for injectable clock, configured-profile loading,
  status aggregation, and period draft filtering.

## Terminology Constraints

Use “CLI” only for Typer command binding, option parsing, rendering, and error
translation. Use “application layer” for `src/aeat/application`; do not use
“app” for that layer because `app` also names Typer objects and command
namespaces. Distinguish setup profile, active CLI profile, `AutonomoProfile`,
and usage-ratio profile. Distinguish filing draft, declaration, local export,
justificante/declaracion import, and filed-state capture. Live submission
remains out of scope. Always qualify “verify” as registry tree verify,
workbook parity verify, export verify, filed-state verify, or declaration
verify.
