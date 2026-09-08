---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:aed745c6554c89e8ac307f1c88a329e97aec007ed88237b6dd83f8f73affc217'
step_id: 'S262'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-only extraction-draft discard mutation and its dedicated test because the live review surface exposes list and view only and no confirmation or abandonment path invokes in-place deletion; retain live read/write and replacement semantics, run focused draft-store and review gates, remeasure exact reachability, update cadence, and write the Step Record.

## Scope

- `extraction draft store discard API and dedicated test`
- `focused draft-store and evidence-review gates`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/ledger/extraction_draft_store.py`
- `M` `src/cadrumo/application/ledger/tests/test_extraction_draft_store.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/ledger/extraction_draft_store.py src/cadrumo/application/ledger/tests/test_extraction_draft_store.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/ledger/tests/test_extraction_draft_store.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_cli.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/ledger/tests/test_extraction_draft_store.py src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_review_cli.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The retained encrypted store and live review surface passed both configured lanes (6 unit and 7 integration tests). Exact unused symbols improved from 284 to 283; 31 unreachable modules and zero orphaned tests remain.
