---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:4babad47e94a07eb636657f5c2bc8791718d85eb907efb01a48972a2003db092'
step_id: 'S263'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the two test-only FieldProvenance construction facades for anchored and self-reported values, their exports, stale module prose, and facade-specific tests; retain the live anchor evaluator, structured-value owner, model-level self-report invariant, and direct behavioral checks, run focused grounding gates, remeasure exact reachability, update cadence, and write the Step Record.

## Scope

- `ledger grounding anchor facades`
- `facade-specific tests and prose`
- `focused grounding tests`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/ledger/grounding_anchor.py`
- `M` `src/cadrumo/application/ledger/tests/test_grounding_anchor.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/ledger/grounding_anchor.py src/cadrumo/application/ledger/tests/test_grounding_anchor.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/ledger/tests/test_grounding_anchor.py src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_reaches_the_operator.py src/cadrumo/entrypoints/cli/tests/test_evidence_field_notices.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/ledger/tests/test_grounding_anchor.py src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py src/cadrumo/entrypoints/cli/tests/test_evidence_provenance_reaches_the_operator.py src/cadrumo/entrypoints/cli/tests/test_evidence_field_notices.py` -> `fail`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The valid focused command passed 87 unit tests. Its integration complement passed 6 and retained two unrelated live operator-envelope failures: untouched fields are stamped asserted and an arithmetic-closure discrepancy is absent. The initial command named a nonexistent neighboring test and collected nothing; it was replaced with the real provenance suites. Exact unused symbols improved from 283 to 281; 31 unreachable modules and zero orphaned tests remain.
