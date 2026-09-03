---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:086a0ca3fad887155c113702bdffc7adfe5012e414ae2cd4303f8b305a5b74d5'
step_id: 'S375'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build the Ledger overview, entries, review, import, classification, evidence, and reconciliation screens over canonical application doors

## Scope

- `src/cadrumo/entrypoints/tui/ledger/`

## Changes
- `A` `src/cadrumo/entrypoints/tui/ledger/`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-slice1-review-audit.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-slice2-review-audit.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-slice3-review-audit.md`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-final-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/ledger/tests` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/ledger src/cadrumo/application/ledger/workspace.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/ledger` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/ledger` -> `pass`
