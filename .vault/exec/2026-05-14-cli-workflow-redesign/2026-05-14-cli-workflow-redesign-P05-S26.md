---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:5cd4c3f31794256c0335f9776e4e2997a8f18f04906c512ba8bfa1b9c166129c'
step_id: 'S26'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Route Modelo 145 command failures through the central command error boundary

## Scope

- `src/aeat/entrypoints/cli`

## Description

- Ground `P05.S26` from the current plan status, semantic search for the CLI error boundary, the decorated Typer tree wiring, and the registered M145 service error-code rows.
- Confirm M145 service exceptions already inherit from the central `AeatError` hierarchy and are registered with stable error codes.
- Add real CLI integration coverage for missing-record validation and invalid local-completion transition failures.
- Assert those failures render through the central JSON error envelope, carry the M145 error codes and categories, and do not leak tracebacks.
- Leave parser, renderer, backend validation, export, persistence, event, and state-transition semantics unchanged.

## Outcome

- `P05.S26` implementation is complete and ready for plan-row closure.
- Verification passed:
  - Focused ruff check for the S26 CLI integration test update: passed.
  - Focused ruff format check for the S26 CLI integration test update: passed.
  - M145 real CLI integration slice, including central error-boundary failures: 6 passed.

## Notes

- No production-code change was required: the existing lazy Typer decoration and registered M145 service errors already route failures through the central boundary.
- The code review found no blocking issues for `P05.S26`.
