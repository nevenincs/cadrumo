---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:290d136b88d97647d9dc854dd2f07385fef5ebaee87df7c820fe91b2d4b98721'
step_id: 'S51'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Rewire extraction recargo aggregation and inventory defaults

## Scope

- `src/cadrumo/application/ledger and src/cadrumo/application/aggregation and src/cadrumo/domain/contribuyente/inventory`

## Changes

- `M` `src/cadrumo/application/ledger/invoice_extraction_authority.py`
- `M` `src/cadrumo/application/ledger/tests/test_invoice_extraction_authority.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/records.py`
- `M` `src/cadrumo/domain/contribuyente/inventory/tests/test_acquisition_cost.py`
- `verify:` `uv run ruff check src/cadrumo/application/ledger/invoice_extraction_authority.py src/cadrumo/application/ledger/tests/test_invoice_extraction_authority.py src/cadrumo/domain/contribuyente/inventory/records.py src/cadrumo/domain/contribuyente/inventory/tests/test_acquisition_cost.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/ledger/invoice_extraction_authority.py src/cadrumo/domain/contribuyente/inventory/records.py` -> `pass`

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
