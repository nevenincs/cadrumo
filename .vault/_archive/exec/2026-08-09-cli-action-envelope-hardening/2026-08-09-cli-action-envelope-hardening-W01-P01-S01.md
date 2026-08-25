---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:452887d229c39b474bfd382cd6dcf7470ec7678520fe7007d0a51a01d4d585dc'
step_id: 'S01'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Add an AST-backed census emitting stable candidate records keyed by path, enclosing symbol, role, alias, and action identity

## Scope

- `dev/cli_action_census.py`

## Description

- Add the pinned-revision AST candidate census in `dev/cli_action_census.py`.
- Emit source-located records with stable `(path, enclosing_symbol, role, alias, action_identity)` keys for definitions, assignments, producers, transformers, and command literals.
- Read the complete production source snapshot through one `git archive` invocation and classify dictionary action aliases as producers.
- Add direct-import, real-source coverage in `dev/tests/test_cli_action_census.py` for stable keys, existing producer shapes, and all three workflow detail-map `next_action` producers.

## Outcome

The initial candidate ledger is deterministic for a pinned revision and does not use line or column locations as its disposition identity. It covers the initial action alias vocabulary, including `recovery_hint`, and records command literals separately. The census completed a direct JSON run for `HEAD` in 11.594 seconds and emitted 1,265 records.

Modified files:

- `dev/cli_action_census.py`
- `dev/tests/test_cli_action_census.py`

## Verification

`uv run --no-sync pytest -n 0 dev/tests/test_cli_action_census.py -q`

`3 passed in 23.07s`

`uv run --no-sync ruff check dev/cli_action_census.py dev/tests/test_cli_action_census.py`

`All checks passed!`

`uv run --no-sync python -m dev.cli_action_census HEAD --json`

`duration_seconds=11.594; candidate_count=1265; candidate_records=1265`

`git diff --check -- dev/cli_action_census.py dev/tests/test_cli_action_census.py`

Exited successfully with no whitespace errors.

## Notes

The initial parallel default test attempt was not accepted as proof after an xdist worker crash. The recorded serial command above is the accepted evidence. No application behavior, external service, or destructive operation was exercised.
