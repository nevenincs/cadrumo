---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:4911c278930d423ffcbd094265d5d0b87596f24e31fc5702628f556401fb77d6'
step_id: 'S253'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the duplicate manual fact-basis projector superseded by live ledger anchor capture

## Scope

- `Remove the unused helper`
- `export`
- `and helper-only tests while retaining the live observation-grounded projector and evidence contracts`
- `run focused aggregation and anchor gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `src/cadrumo/application/aggregation/ledger_filing_snapshot.py`
- `M` `src/cadrumo/application/aggregation/tests/test_ledger_filing_snapshot.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/aggregation/ledger_filing_snapshot.py src/cadrumo/application/aggregation/tests/test_ledger_filing_snapshot.py src/cadrumo/application/modelo/_ledger_anchor_capture.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aggregation/tests/test_ledger_filing_snapshot.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/modelo/tests/test_ledger_evidence_recapture.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
