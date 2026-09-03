---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:88b005b365ccb26e8b1a94b4f6519cf93a6157f41e8fbe5794ddbfc2a0c5bab1'
step_id: 'S391'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Define an immutable Ledger workspace projection and public affected-declaration reconciliation provider from canonical Ledger, invoice-link, and filing-staleness authorities

## Scope

- `src/cadrumo/application/ledger/workspace.py`

## Changes
- `A` `src/cadrumo/application/ledger/workspace.py`
- `A` `src/cadrumo/application/ledger/tests/test_workspace.py`
- `R` `src/cadrumo/application/aggregation/_ledger_filing_snapshot.py` -> `src/cadrumo/application/aggregation/ledger_filing_snapshot.py`
- `M` `src/cadrumo/application/aggregation/__init__.py`
- `M` `src/cadrumo/application/modelo/verification.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s391-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/ledger/tests/test_workspace.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/ledger/workspace.py src/cadrumo/application/ledger/tests/test_workspace.py src/cadrumo/application/aggregation/ledger_filing_snapshot.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/ledger/workspace.py src/cadrumo/application/aggregation/ledger_filing_snapshot.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/ledger/workspace.py src/cadrumo/application/aggregation/ledger_filing_snapshot.py` -> `pass`
