---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:95cb55b9e7cbe357f115e5d442e14b630f66fd3292e199beb0d9cdc0372841fc'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S206]]"
---

# `reachability-burndown` audit: `S206 calendar censo enrolment accessor withdrawal review`

## Scope

Independent bounded review of W05.P12.S206: removal of the test-only census accessor/export, retained private runtime authority and public applicability computation, black-box Modelo 303/202 proofs, cadence addition, and Step Record evidence.

## Findings

No findings.

The private `_CENSO_ENROLMENT_PROFILE_KEYS` remains the live intersection authority used by calendar warning classification. `calendar_applicability_profile_keys_for_modelo` remains public and production-used. The deleted accessor had no production caller and exposed the private set only for a census-style test.

The rewritten tests no longer introspect the production census. Shared test constants deduplicate fixture inputs for each modelo; missing-one-key cases retain warnings and complete-key cases clear them for both 303 and 202. Separate applicability assertions establish prerequisite coverage without deriving expected membership from the private set, so the behavioral proofs retain detector teeth. Production imports no test or development module.

The Step Record gives exact changed paths, Ruff, isolated-basetemp focused test, target residue, metastate, and live reachability commands. Four focused tests pass. It records the live 65/322/18 and 2028-of-2094 graph and explicitly declines to attribute concurrent aggregate drift to S206.

## Recommendations

Approve W05.P12.S206. No code or evidence correction is required.
