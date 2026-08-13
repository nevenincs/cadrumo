---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:407d5b6597c78b34979ce1decabaa56fc9d2a314a350bca5e57caa2beaf3eca1'
step_id: 'S39'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Prove repeated overview notices retain their exact text, envelope, action, and provenance while one invocation performs bounded live descriptor and reconciliation construction.

## Scope

- `src/cadrumo/entrypoints/cli/tests`
- `src/cadrumo/application/operator_surface/tests`

## Description

- Invoke the public JSON `app overview status` route twice against the deterministic active-profile fixture.
- Assert the two strict envelope documents remain semantically identical, including ordered notice text, context, actions, and action-binding provenance.
- Decode each emitted typed notice action from its JSON wire form and resolve the original action and bindings through one separate real Click root invocation.
- Assert semantic and serialized-byte equality between the captured ordered actions and their freshly resolved counterparts.
- Retain the canonical malformed invocation-cache refusal proof and the upstream Click and vendored Typer lifecycle proof from S38.
- Measure CPU and wall time separately, enforcing S37's CPU ceiling `(9.495 + healthy overview CPU) * 1.64`.

## Outcome

The public overview route retained the same strict envelope across two deterministic roots. Its ordered action-bearing notices, including text, context, action identity, command path, and binding provenance, were exactly preserved. Resolving those captured actions through one independent real Click root produced semantically equal typed actions and identical serialized action bytes, without a per-notice live-surface rebuild.

The bounded measurement passed: baseline `21.672` CPU seconds and `22.574` wall seconds; healthy overview CPU was `12.177` seconds after the S37 `9.495`-second reconciliation cost; the resulting CPU ceiling was `35.542` seconds. The following root completed in `3.219` CPU seconds and `3.270` wall seconds. CPU, not wall time, determines the acceptance gate.

Focused proof passed: the public overview action/equivalence test passed in `36.37` seconds; the S38 real Click and vendored Typer lifecycle suite passed two tests in `19.68` seconds; and the malformed-cache refusal test passed in `4.70` seconds. Ruff check, Ruff format check, and scoped diff hygiene all passed for the two S39-owned test modules.

## Notes

The first comparison design called the fresh resolver outside an invocation for every action and exceeded the bounded command allowance. The final proof keeps the independent comparison inside one real Click root, matching the canonical invocation lifecycle and avoiding the superseded repeated-build pattern. No production code, runtime behavior, action catalogue, or descriptor construction path was changed by S39.
