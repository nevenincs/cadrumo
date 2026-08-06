---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
body_hash: 'sha256:e9bc6fd13ca0f50204f765ff8559a1b82dcc776effaf56d89a8f5166be736bc3'
step_id: 'S431'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Render typed Period values through the canonical display form on overview and ledger read surfaces

## Scope

- `src/aeat/entrypoints/cli/_overview.py`
- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/entrypoints/cli/tests/test_overview_verbs.py`
- `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`

## Description

- Ground the change with `vaultspec-rag`, then read the overview status, ledger check/preflight/status rendering paths, the `Period` display authority, and the real CLI integration tests.
- Replace the reversed hand-rendered `<token> <year>` strings with `str(Period)` for overview status and ledger check, preflight, and status output.
- Preserve JSON schemas that deliberately carry raw `filing_year` plus `code` fields, notice contexts that carry bare `period` plus `year`, and machine-readable ledger fields that require raw registry tokens.
- Add real isolated-encrypted CLI parity coverage: overview status text and JSON agree on the canonical display; ledger check, preflight, and status text agree; check JSON carries its display-list contract while preflight JSON retains its raw schema shape.

## Outcome

Operator-facing typed filing periods now render only through `Period.__str__` as `YYYY <token>` (for example, `2026 1T`), instead of the previous reversed `1T 2026`. Transport fields remain deliberately structured where their schema contracts require `filing_year` and `code` separately; no raw schema or notice context changed. The tests drive the mounted CLI commands against real isolated encrypted profile storage and backend services, without mocks, stubs, patches, or monkeypatches.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/_ledger_read_cli.py src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_overview_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py src/aeat/entrypoints/cli/tests/test_ledger_preflight_verb.py src/aeat/entrypoints/cli/tests/test_ledger_link_check_verbs.py -q` — 41 passed.

## Notes

The default test command selects `unit` tests, so this CLI evidence intentionally overrides the marker with `-m integration`. `ledger check` has a display-list JSON contract (`periods`), while preflight retains its structured raw `filing_year`/`code` payload and notice context. The plan checkbox remains open for independent review.
