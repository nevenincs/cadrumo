---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f354c78b2714054d21ba1a95cc06d48719045c08ee5910025572e249b9c8e17a'
step_id: 'S45'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Run every production-registered executor through the shared success, refusal, failure, interaction, cancellation-capability, deadline-capability, effect, and cleanup matrix and prove the exported definition population is complete

## Scope

- `src/cadrumo/entrypoints/tests/test_registered_executor_conformance.py`
- `src/cadrumo/application/operations/_supervisor.py`
- `src/cadrumo/application/operations/tests/test_supervisor.py`
- `src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py`

## Description

- Preserved the authoritative relocated entrypoint conformance module; the former application test path remains absent.
- The one data-driven public-services matrix executes all thirteen production definitions through fresh composed runtime state, rather than inspecting declaration metadata or factory construction.
- Each row asserts its observed exact terminal condition and effect. The two refusal rows also assert their exact registered public refusal reference; the Google failure asserts its durable diagnostic reference.
- The Google case uses Modelo 130 / 2025 / 1T with the canonical unconfigured transport and asserts the actual ordered owner sequence `preflight`, `plan`, `apply` before the transport failure. The absent settlement phase is therefore adversarially proven.
- CENSO cancellation and execution-deadline cases use public cancellation, response, and observation services and await the terminal projection. They prove manual cancellation settles `CANCELLED`/`NONE`, deadline cancellation settles `TIMED_OUT`/`NONE`, both retain acknowledgement and cleanup-deadline facts, and the owned resource is closed.
- The canonical supervisor now turns a completed executor that has durably acknowledged cancellation into its sole truthful terminal receipt: `CANCELLED` for a manual request and `TIMED_OUT` when the cancellation request is at or after the persisted execution deadline. It retains the executor's observed effect and preserves cleanup-before-receipt settlement.

## Outcome

- The production inventory remains the complete thirteen-definition population composed by the canonical entrypoint registry builder.
- Exact observed rows include: auth configure `SUCCEEDED`/`UPDATED`; auth acquire `REFUSED`/`UNKNOWN` with `REFUSED_AUTH_LOGIN_LIVE_TESTS_DISABLED`; auth logout and reset `SUCCEEDED`/`NONE`; bundle export `SUCCEEDED`/`UPDATED`; filed history `REFUSED`/`NONE` with `REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED`; and Google `FAILED`/`UNKNOWN`.
- CENSO's interaction, manual-cancellation, deadline, effect, and cleanup paths all complete through the actual public composed services.

## Verification

- `uv run --no-sync pytest -q -n 0 --timeout=90 -m integration src/cadrumo/entrypoints/tests/test_registered_executor_conformance.py` - 15 passed in 106.22s.
- `uv run --no-sync pytest -q -n 0 --timeout=60 -m integration src/cadrumo/application/operations/tests/test_supervisor.py` - 50 passed in 50.71s.
- `uv run --no-sync pytest -q -n 0 --timeout=60 -m integration src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py` - 9 passed in 9.33s.
- `uv run --no-sync pytest -q -n 0 --timeout=90 -m integration src/cadrumo/entrypoints/tests/test_operation_composition.py` - 7 passed in 8.08s.
- Focused Ruff check and format check passed over the S45 supervisor and test surface.
- `uv run --no-sync ty check src/cadrumo/application/operations/_supervisor.py src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py src/cadrumo/entrypoints/tests/test_registered_executor_conformance.py` - passed.
- `git diff --check` passed over the residual S45 paths.

## Review

- Third independent review approved S45 after verifying exact public terminal/effect/refusal/failure behavior, ordered Google phase evidence, and supervisor-owned cooperative cancellation/deadline settlement.

## Notes

- RAG discovery grounded the automatic terminal receipt in the supervisor's durable acknowledgement, execution deadline, cleanup-deadline, and stopped-task invariants. No private supervisor test harness, compatibility surface, or cross-owner fixture was introduced.
- Shared HEAD `477159db8b` already contains the supervisor settlement implementation and its canonical tests alongside custody work. The corrective S45 commit `7afd4c5113` contains the subsequent exact-entrypoint and lifecycle-test refinements; history was not rewritten.
- The S45 plan checkbox is closed after third independent-review approval.
