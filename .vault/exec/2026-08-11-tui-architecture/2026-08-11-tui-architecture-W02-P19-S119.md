---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b1fd205244bdf0c8e2605e344cb7ec2e7d1fd8b5059fc047569ac80d1b218429'
step_id: 'S119'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement the public observation service and deterministic progress fold with phase reset, independent lifecycle-terminal-effect projection, bounded cursor replay, cursor-ahead refusal, expiry or compaction resynchronization, detach, and reconnect semantics

## Scope

- `src/cadrumo/application/operations/_observation.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/operations/tests/test_observation.py`
- `src/cadrumo/application/operations/tests/test_facade.py`

## Description

- Compose one stateless public observation service over the application-owned atomic reader and immutable registry.
- Dispatch the current observation version before exact request handling and collapse unknown, cursor-ahead, contract-drift, invalid, and unavailable states into closed safe refusals.
- Fold current progress from the authoritative checkpoint suffix, clearing on phase changes and replacing on later progress through the anchor.
- Project lifecycle, terminal condition, effect, phase, deadlines, cancellation facts, settlement references, and pending interaction independently without persistence or response-authority leakage.
- Convert each bounded replay row through one canonical raw-event-to-public-event projector and preserve page, caught-up, expired, and compacted cursor semantics.
- Export the service from the sole operations facade and extend its structural contract test.
- Prove bounded detach/reconnect and read-only byte identity through the real filesystem journal adapter; prove expiry and compaction replacement from exact checkpoints.

## Outcome

- `OperationObservationService` is the sole public observation producer and is reusable by every inbound frontend.
- Projection and replay share the one atomic anchor supplied by `OperationObservationReader`.
- Progress survives bounded pages and resynchronization without becoming snapshot or frontend authority.
- Fresh service instances can reconnect from a returned cursor without mutation or response capability reconstruction.
- Post-edit semantic discovery and exact symbol census converge on one service, one progress fold, and one safe event projector with no frontend snapshot/replay join.

## Verification

- Focused Ruff and `ty` checks pass.
- Public observation, DTO, materialization, and real persistence journal tests: 96 passed.
- Operation application plus persistence suites excluding one independently stale concurrent persistence-facade inventory assertion: 290 passed.
- Import-hygiene scan passes.
- Focused collection: 4 tests collected cleanly.

## Notes

The full combined operation suite has one unrelated concurrent failure in the persistence-operation facade export inventory: its expected list has not yet incorporated the canonical secure-reference namespace and repository factory already present in the facade. S119 does not own or alter that persistence export surface. The plan step remains open for parent sequencing after independent review.
