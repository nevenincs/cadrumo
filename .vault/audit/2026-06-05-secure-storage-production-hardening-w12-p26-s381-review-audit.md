---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S381]]'
---

# `secure-storage-production-hardening` Code Review

## S381-001 | PASS | CLI boundary preserves typed AEAT runtime refusals

`command_error_boundary` forwards typed `AeatError` instances unchanged and has a dedicated stored-data drift branch before the broad AEAT branch. This keeps storage/runtime/master-key refusals on registered error codes and translated messages rather than generic internal failures.

Evidence:
- `src/aeat/entrypoints/cli/_errors.py:70`
- `src/aeat/entrypoints/cli/_errors.py:104`
- `src/aeat/entrypoints/cli/_errors.py:133`
- `src/aeat/entrypoints/cli/_errors.py:176`
- `src/aeat/entrypoints/cli/_errors.py:225`
- `src/aeat/entrypoints/cli/_errors.py:235`

## S381-002 | PASS | Nested storage errors are unwrapped before fallback

The unexpected-exception arm preserves Click/Typer control flow, then checks `_unwrap_aeat_error` before logging and wrapping as `CliUnexpectedBoundaryError`. `_unwrap_aeat_error` walks SQLAlchemy-style `orig` plus standard cause/context chains with a depth bound, so storage exceptions raised inside library machinery remain typed refusals.

Evidence:
- `src/aeat/entrypoints/cli/_errors.py:253`
- `src/aeat/entrypoints/cli/_errors.py:268`
- `src/aeat/entrypoints/cli/_errors.py:271`
- `src/aeat/entrypoints/cli/_errors.py:431`
- `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py:41`
- `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py:55`
- `src/aeat/entrypoints/cli/test_error_boundary_unwrap.py:68`

## S381-003 | PASS | Rendering remains centralized and redacted

`_emit_error_and_exit` renders errors through the core registry JSON/text renderers, `write_stderr` redacts CLI output before writing, and `_errors.py` does not read environment variables or settings directly.

Evidence:
- `src/aeat/entrypoints/cli/_errors.py:338`
- `src/aeat/entrypoints/cli/_errors.py:301`
- `src/aeat/entrypoints/cli/test_errors_boundary.py:125`
- `src/aeat/entrypoints/cli/test_root_fallback_write_guard.py:173`

## S381-004 | PASS | Validation and RAG grounding completed

Validation passed for focused lint, CLI error-boundary coverage, root fallback write-guard coverage, and locale audit. Vaultspec RAG search confirmed the boundary unwrap tests, CLI error boundary implementation, and registered storage runtime refusals as the relevant surfaces.

Commands:
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_errors.py src/aeat/entrypoints/cli/test_error_boundary_unwrap.py src/aeat/entrypoints/cli/test_error_boundary_integration.py src/aeat/entrypoints/cli/test_errors.py src/aeat/entrypoints/cli/test_errors_boundary.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_error_boundary_unwrap.py src/aeat/entrypoints/cli/test_error_boundary_integration.py src/aeat/entrypoints/cli/test_errors.py src/aeat/entrypoints/cli/test_errors_boundary.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "CLI error boundary unwrap AeatError StatementError NoActiveBucketSession master key storage runtime refusal" --type code --port 8766 --max-results 8`

## S381-005 | PASS | Independent reviewer found no blocking issues

The `vaultspec-code-reviewer` persona reported no blocking issues. It confirmed direct `AeatError` forwarding, library-wrapped `AeatError` unwrapping before unexpected-error logging, registered error rendering via `tr`, and S381 plan closure. It also noted a LOW hygiene point: `test_errors.py` contains a source-marker assertion for cast-rationale comments; that test is not counted above as behavioral evidence for runtime boundary correctness.
