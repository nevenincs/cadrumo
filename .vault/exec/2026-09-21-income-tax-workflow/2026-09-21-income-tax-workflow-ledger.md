---
tags:
  - '#exec'
  - '#income-tax-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:26bdb1d8455ca44970f999103d2ff1e132bafc63a576951f8db7bce32c77c711'
related:
  - "[[2026-09-21-income-tax-workflow-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `income-tax-workflow` ledger

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
- `S01` `A` `dev/acceptance/__init__.py`
- `S01` `A` `dev/acceptance/income_tax/__init__.py`
- `S01` `A` `dev/acceptance/income_tax/authority.py`
- `S01` `A` `dev/acceptance/income_tax/tests/__init__.py`
- `S01` `A` `dev/acceptance/income_tax/tests/test_authority.py`
- `S01` `verify:` `python -m dev.acceptance.income_tax.authority --latest-supported --as-of 2026-09-21` -> `pass`
- `S01` `verify:` `python -m pytest -q dev/acceptance/income_tax/tests/test_authority.py` -> `pass`
- `S01` `verify:` `ruff check dev/acceptance/income_tax` -> `pass`

## Notes

- `S01` M100/2025 XML export is deliberately blocked: application.filing.export_parity.errors.aux_block_undeclared (aux_version); no value was invented.
