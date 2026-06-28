---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S381'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S381 CLI error boundary

## Scope

- `src/aeat/entrypoints/cli/_errors.py`

## Description

- Audited the CLI error boundary against the target `runtime-default` for `master-key` signal handling.
- Confirmed `command_error_boundary` forwards typed `AeatError` instances, wraps stored profile drift separately from input-time validation, and unwraps nested `AeatError` instances from library exception chains before falling back to unexpected-error handling.
- Confirmed unexpected exceptions are logged with traceback before being wrapped, while Click/Typer control-flow exceptions propagate.
- Confirmed emitted CLI errors route through registered core error rendering and redacted stderr output; `_errors.py` has no direct environment or settings access.
- Validated the existing boundary, unwrap, root fallback, and locale surfaces with focused tests.

## Outcome

- AFR-279 closed: `_errors.py` is the centralized translated CLI boundary for runtime/storage/master-key refusals and does not require production code changes.
- The plan checkbox was closed through `vaultspec-core vault plan step check` for `S381`; the AFR-279 register row was reconciled to `closed`.
- Validation passed: focused ruff, error-boundary tests, root fallback write-guard tests, locale audit via `python -m aeat.locales audit`, and vaultspec RAG search for the CLI error boundary/runtime refusal path.

## Notes

- `src/aeat/entrypoints/cli/_app_live.py` remains dirty from concurrent live IVA watchdog/auth work and was intentionally left untouched.
- The modelos repository cluster remains active in the shared worktree and was intentionally left untouched.
