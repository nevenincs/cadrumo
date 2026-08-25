---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d81792cca40337152bf3e07b5e048309dc5b1586f03d51b7a7c4549aa49d5113'
step_id: 'S02'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Add fixed-point vocabulary expansion and fail a closing pass that discovers a new semantic cluster

## Scope

- `dev/cli_action_census.py`

## Description

- Keep the fixed-point candidate denominator on the exact S01 production Python scope.
- Add an explicit production source bundle and parse locale catalogue YAML scalar values instead of raw prose.
- Replace global representative triggers with local AST data-flow evidence and isolate nested lexical scopes.
- Persist strict JSON-v1 fixed-point state carrying revision, scope, scan aliases, and admitted cluster keys.
- Add state load, write, cluster acknowledgement, rescan, and close operations to the diagnostic CLI.
- Separate cluster acknowledgement from scan-vocabulary promotion; require each promoted alias to have locally evidenced `ACTION_ALIAS` discovery evidence.
- Add direct positive and negative regression coverage for causal triggers, comments, nested scopes, generic tokens, promotion, reopening, rejection, and state round-trips.

## Outcome

The census now reports only production evidence, retains the S01 denominator through cluster acknowledgement, and refuses closure whenever a real newly observed cluster remains. Cluster acknowledgement records reviewed evidence without treating model, helper, renderer, refusal, result, or message labels as scan aliases. A separate repeatable `--admit-alias` transition rejects tokens without local action-alias evidence; promotion can intentionally expand the next pass and expose new evidence for review.

## Verification

`uv run --no-sync pytest -n0 dev/tests/test_cli_action_census.py -q`

`10 passed in 34.65s`

`uv run --no-sync ruff check dev/cli_action_census.py dev/tests/test_cli_action_census.py`

`All checks passed!`

`uv run --no-sync basedpyright dev/cli_action_census.py dev/tests/test_cli_action_census.py`

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync python -m dev.cli_action_census HEAD --fixed-point --write-state <seed-state> --json`

The production observation completed with exit code 0 in 30.15 seconds: 1,265 candidates, 659 discoveries, 659 newly observed clusters, seven seed aliases, and zero admitted cluster keys.

`uv run --no-sync python -m dev.cli_action_census HEAD --fixed-point --state <seed-state> --admit-observed --write-state <admitted-state> --json`

The artifact-producing process completed after its supervising 60-second wrapper timed out. Its persisted output reports 1,265 candidates, 659 discoveries, zero newly observed clusters, seven unchanged aliases, and 659 admitted cluster keys.

`uv run --no-sync python -m dev.cli_action_census HEAD --fixed-point --state <admitted-state> --close-fixed-point`

`revision HEAD`

`action-guidance candidates 1265`

`fixed-point discoveries 659`

`unadmitted discoveries 0`

`unknown clusters 0`

The closing command exited 0 in 30.03 seconds.

## Notes

The first supervised cluster-admission command reached its 60-second host timeout after writing complete result and state artifacts. Its process had exited before artifact inspection; its command exit status is therefore not independently available. The final loaded-state closing command independently completed with exit code 0.
