---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:51b773cdba61453d13f88214e22f640824d5c5ded97efc7193eff61e2583fe21'
step_id: 'S229'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unused slim InvoiceListRow projection, its two zero-consumer catalogue row builders, and the two self-tests that only preserve them; retain the canonical rich Invoice aggregate, the live ledger.invoice.list payload, and the production-used repository link-consistency query and its real storage-boundary test.

## Scope

- `Application invoice catalogue reads and focused tests`
- `live CLI invoice list projection`
- `accepted canonical invoice structure decision`
- `exact symbol signal`
- `focused invoice gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `M` `src/cadrumo/application/invoices/catalogue_reads.py`
- `M` `src/cadrumo/application/invoices/tests/test_queries.py`
- `M` `src/cadrumo/application/invoices/__init__.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/invoices/catalogue_reads.py src/cadrumo/application/invoices/tests/test_queries.py src/cadrumo/application/invoices/__init__.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s229 src/cadrumo/application/invoices/tests/test_queries.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s229-cli src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "not unit" --basetemp .tmp/pytest-s229-cli-held src/cadrumo/entrypoints/cli/tests/test_business_invoice_verbs.py src/cadrumo/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit exits 1 on the remaining backlog, as designed. This step reduced reachable-module unused-symbol findings from 305 to 304 while leaving 51 unreachable modules and four orphaned test modules unchanged. Three production names were removed, but only `list_invoice_rows` was an exact finding; the DTO and private projector were already cleared by other audit rules. The retained repository link query has a production caller and its two focused consistency tests pass.
