---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7c3d27e30935406330e1e8d66e6333e7cfc9977b60f9bc7ef868a62a690224db'
step_id: 'S40'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Register profile field mutation, repeatable-row mutation, bundle export, and profile logout operations through existing user-profile authorities

## Scope

- `src/cadrumo/application/user_profile/_operation_definitions.py`
- `src/cadrumo/application/user_profile/tests/test_operation_definitions.py`
- canonical executor-owner protocol relocation required by the S40 review

## Description

Validated the single canonical four-definition `USER_PROFILE_OPERATION_DEFINITIONS` population. Its scalar field, repeatable-row, bundle-export, and strong profile-logout executors each bind the exact active `profile:<UUID>` subject, publish supervisor lifecycle facts, and delegate once to the existing user-profile authority. The bundle exporter uses only the S114 one-shot secret channel and existing durable export publisher/journal; none of the executors recreates a write, export, session-close, or storage path.

Resolved the review's high canonical-home finding by moving the actual executor protocol implementation to `application.operations.owner` and deleting its former forwarding module. The user-profile executor imports remain directed at that one owner; no executor contract is redeclared in the profile operation module.

## Outcome

- The profile-operation registry exposes exactly one definition for each required family, with secure-reference custody, definition-subject conflict scope, honest `NONE`/`UPDATED`/`UNKNOWN` effects, interrupt reconciliation, and all CLI/MCP/TUI projections.
- Real supervisor proofs cover encrypted request/result custody, scalar mutation, schema row allocation, one-shot export-passphrase zeroisation and durable publication, and strong profile close after request resolution.
- Semantic RAG located the canonical operation owner and current authorities; exact `rg` census confirmed one profile operation population and no stale `_executor` imports after the relocation.
- Independent review approved the executor-owner relocation and the S40 operation surface. The direct CLI custody logout invocation is tracked exclusively by `W06.P14.S157`; manager direct doors remain owned by `W06.P14.S76` and `W06.P14.S77`.

## Verification

- `uv run --no-sync pytest -q -n0 -m integration src/cadrumo/application/user_profile/tests/test_operation_definitions.py`: 5 passed.
- `uv run ruff check src/cadrumo/application/operations/owner.py src/cadrumo/application/user_profile/_operation_definitions.py src/cadrumo/application/user_profile/tests/test_operation_definitions.py`: passed.
- `uv run --no-sync pytest -q -n0 -m unit src/cadrumo/application/operations/tests/test_facade.py`: 5 passed.
- `git diff --check` over the owner relocation and S40 surface: passed.

## Notes

S40 registers and proves the application-owned executors. Frontend cutovers are separate downstream deletion steps; no compatibility shim or parallel executor remains in the S40-owned surface.
