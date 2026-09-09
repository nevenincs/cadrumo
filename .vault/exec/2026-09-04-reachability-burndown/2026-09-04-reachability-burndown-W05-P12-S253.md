---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f2d7b0de05bf5a12049a366ba0c6745b438b2c2ae48925b4a6c3d597e319fabf'
step_id: 'S253'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

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
