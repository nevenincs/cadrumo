---
tags:
  - '#exec'
  - '#ledger-interface-contract'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
---

# `ledger-interface-contract` `W03.P05` summary

Closed the remaining typed list/read row payload migration and verified the C5 owner surface after the deferred D2 remainder landed.

- Modified: `src/aeat/entrypoints/cli/_ledger_payloads.py`
- Modified: `src/aeat/entrypoints/cli/_ledger_export_cli.py`
- Modified: `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`
- Modified: `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`
- Modified: `src/aeat/entrypoints/cli/_ledger_inventory_cli.py`
- Modified: `src/aeat/entrypoints/cli/_ledger_evidence_cli.py`
- Modified: `src/aeat/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py`

## Description

The deferred D2 payload remainder is now represented by Step Records for `S23` through `S30`, and every row/list boundary named in `W03.P05` is closed in the plan. The previous code-review concern about missing peer execution records is no longer current: records for `S05` through `S09` are present in the C5 exec directory.

Verification on 2026-06-12:

- `uv run --no-sync pytest src/aeat/domain/transactions/tests/test_repository_roundtrip.py src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py src/aeat/entrypoints/cli/tests/test_ledger_list_sort.py -m "integration or not integration" -q` passed `79/79`.
- `uv run --no-sync ty check` on the C5 ledger CLI files passed with zero diagnostics.
- `uv run --no-sync pyright` on the C5 ledger CLI files passed with zero diagnostics.

The global `just check-types` gate remains red from non-ledger baseline diagnostics in calculation/modelo tests and is recorded in the ledger hardening close audit rather than attributed to C5.
