---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:2da291ff7b0438c3b2557d304f309afdf38b6e7a342d6329ce45858dc3b8163f'
step_id: 'S119'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Implement the public observation service and deterministic progress fold with phase reset, independent lifecycle-terminal-effect projection, bounded cursor replay, cursor-ahead refusal, expiry or compaction resynchronization, detach, and reconnect semantics

## Scope

- `src/cadrumo/application/operations/_observation.py`
- `src/cadrumo/application/operations/_journal.py`
- `src/cadrumo/application/operations/_execution_context.py`
- `src/cadrumo/application/operations/_supervisor.py`
- `src/cadrumo/application/operations/_registry.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/user_profile/_censal_operation.py`
- focused application and persistence operation tests

## Description

- Compose one stateless public observation service over the application-owned atomic reader and immutable registry.
- Dispatch the current observation version before exact request handling and collapse unknown, cursor-ahead, contract-drift, invalid, corrupt, and unavailable states into closed safe refusals.
- Fold current progress from the authoritative checkpoint suffix, clearing on phase changes and replacing on later progress through the anchor.
- Project lifecycle, terminal condition, effect, phase, deadlines, cancellation facts, settlement references, and pending interaction independently without persistence or response-authority leakage.
- Convert each bounded replay row through one canonical raw-event-to-public-event projector and preserve page, caught-up, expired, and compacted cursor semantics.
- Advance the current-only journal snapshot to schema v6 with one required `cancellation_deferred` fact, persisted by supervisor-owned nested irreversible-section enter and exit transitions, so `cancellable_now` is an observed fact rather than a lifecycle guess.
- Bind every projected pending interaction to the registered kind and bind REVIEW response schema references through the registry-owned canonical schema-reference formatter.
- Give the censal definition one strict authority-free review-response DTO and one reusable schema binding; derive its durable interaction reference from that binding instead of redeclaring the wire string.
- Export the service, schema-reference formatter, and censal response contract through their sole package facades and extend structural contract tests.
- Prove bounded detach/reconnect and read-only byte identity through the real filesystem journal adapter; prove expiry and compaction replacement from exact checkpoints.

## Outcome

- `OperationObservationService` is the sole public observation producer and is reusable by every inbound frontend.
- Projection, current cancellation availability, progress and replay share durable state under the atomic observation anchor.
- Progress survives bounded pages and resynchronization without becoming snapshot or frontend authority.
- Fresh service instances reconnect from a returned cursor without mutation or response capability reconstruction.
- REVIEW observation exposes only registered safe identity and schema facts; mismatched durable checkpoints fail closed.
- Post-edit semantic discovery and exact symbol census converge on one service, one progress fold, one safe event projector, one cancellation-availability transition owner, one schema-reference formatter, and one censal response-schema binding with no frontend snapshot/replay join or production schema-string redeclaration.

## Verification

- Ruff and focused `ty` checks pass across the application operation package, persistence operation adapter, and final censal schema-binding surface.
- Full operation application and persistence unit plus integration lanes, excluding one independently stale persistence-facade inventory assertion: 378 passed.
- Explicit real supervisor irreversible-section observation witness: 1 passed.
- Focused public observation real-adapter suite: 6 passed, covering all nine event variants, safe interactions, terminal axes, reconnect, corrupt-read collapse and both resynchronization dispositions.
- Final censal facade, real durable executor parity, and observation tests: 10 passed.
- Import-hygiene scan passes.
- Independent review found two HIGH and one MEDIUM issue; all were remediated. A later fixed-point review found the sole production schema-reference redeclaration; it was removed and returned for a final fresh review.

## Notes

The combined operation suite has one unrelated concurrent failure in the persistence-operation facade export inventory: its expected list has not yet incorporated the canonical secure-reference namespace and repository factory already present in the facade. Three selected censal integration modules also remain blocked before execution by their known pre-S122 uncomposed registry fixtures, which fail at the definition-contract pin introduced in S117 rather than at S119 behavior. The repository-wide Vault check remains red on unrelated existing corpus errors; this Step record itself is CLI-attested. The plan step remains open for parent sequencing after final review.
