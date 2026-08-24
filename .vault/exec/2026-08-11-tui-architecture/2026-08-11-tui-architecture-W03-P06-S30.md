---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:aa8335bfa8d22729634e99299ff1e843e9043ce681684bf9f4169dab2a5a022e'
step_id: 'S30'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Persist the encrypted reviewed observation, baseline revision and digest, field intents, and proposed-effect digest behind a secure reference

## Scope

- `src/cadrumo/application/user_profile/_censal_observation.py`
- `src/cadrumo/application/user_profile/_censal_operation.py`
- `src/cadrumo/application/user_profile/_censo_sync.py`
- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py`
- Narrow direct parser and secure-reference tests

## Description

- Promote the exact censal read projection to a strict immutable application-owned public contract.
- Make the outbound parser construct that canonical contract directly, with no adapter DTO, bridge, or duplicate schema.
- Bind the proposal to the canonical profile identity, record revision, and self-verifying record content digest.
- Require one explicit adopt-or-preserve intent for every canonical adoptable profile path, exactly once and in canonical order.
- Derive and verify the proposed-effect digest over the complete observation, baseline, and field-intent preimage.
- Prove strict JSON serialization and encrypted content-addressed secure-reference round trips with real storage adapters.
- Prove empty, partial, duplicate, extra, reordered, intent-tampered, and substituted payloads fail through production validation boundaries.

## Outcome

- The reviewed proposal is one domain-owned immutable operand suitable for supervisor secure publication; no second store or journal was introduced.
- The application layer no longer imports the outbound censal DTO, and the parser emits the application contract directly.
- Every adoptable path has an explicit, deterministic review decision.
- Sensitive censo identity and name values remain absent from database bytes at rest.
- Focused application and parser tests, Ruff, BasedPyright, and diff integrity checks passed; import-linter no longer reports the censal operand adapter edge.

## Notes

- This Step adds no acquisition, orchestration, apply, TUI, or CLI behavior.
- The redundant BeautifulSoup `Tag` checks were replaced by one fail-closed runtime shape validator; the focused parser/operand BasedPyright lane is clean. The all-touched-file invocation still reports 12 pre-existing diagnostics in the live and user-profile facades/censo apply typing, with no parser diagnostic.
- The shared plan checkbox was intentionally left unchanged for the coordinating session.
