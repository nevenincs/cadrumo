---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---



# Observability store persistence closeout audit

## Scope

This closeout covers W12.P26.S301, W12.P26.S302, W12.P26.S305, W12.P26.S306, and W12.P26.S308.

| Row | AFR | Module | Disposition |
| --- | --- | --- | --- |
| W12.P26.S301 | AFR-199 | `observability.__init__` | public API export reviewed |
| W12.P26.S302 | AFR-200 | `observability._context` | hardened remote-mirror boundary |
| W12.P26.S305 | AFR-203 | `observability._models` | accepted diagnostic model plaintext exception |
| W12.P26.S306 | AFR-204 | `observability._recorder` | accepted diagnostic recorder plaintext exception |
| W12.P26.S308 | AFR-206 | `observability._store` | hardened remote-mirror boundary |

## Findings

- `observability.__init__` remains an explicit public API barrel for strict trace models, replay, store accessors, and registered observability exceptions. It now exports the persistence failure class so callers can catch the complete AEAT observability hierarchy.
- `observability._models` defines frozen, strict pydantic records and closed enums. The model layer documents the diagnostic-data sensitivity contract and does not write files, open remote mirrors, or bypass the redaction substrate.
- `observability._recorder` remains a single emit primitive. Missing run context raises a registered AEAT exception, and event emission uses structured logging with `run_event` payloads for the JSONL sink.
- `observability._context` no longer creates the per-run directory directly. It routes the directory creation through the store boundary so filesystem failures are raised as registered AEAT observability exceptions, and replay marker fallback now leaves a debug breadcrumb instead of silently omitting the value.
- `observability._context` now fails closed on successful command exits when final `trace.json` persistence fails, while preserving an already-propagating body exception so trace persistence does not mask the primary failure path.
- `observability._store` now wraps filesystem create/read/write failures as `RunTracePersistenceError`, a registered core AEAT exception with locale-backed operator rendering. `iter_runs` now logs skipped non-run, non-directory, missing-trace, unreadable, and invalid-trace entries instead of silently discarding them.

## Closeout Rationale

The observability run-trace files are diagnostic artefacts, not profile/session/model ledger stores. They remain plaintext diagnostic JSON/JSONL after DIAGNOSTIC-class redaction because replay and support inspection need deterministic local files. The hardened boundary keeps that exception explicit:

- write and read failures are typed AEAT failures rather than raw `OSError`;
- skip paths are observable at debug or warning level;
- strict model validation remains the schema gate;
- persisted event and trace leaves continue through diagnostic redaction before serialization.

## Validation

- `uv run ruff check src/aeat/core/observability/__init__.py src/aeat/core/observability/_context.py src/aeat/core/observability/_errors.py src/aeat/core/observability/_models.py src/aeat/core/observability/_recorder.py src/aeat/core/observability/_store.py src/aeat/core/observability/test_sink.py src/aeat/core/errors/registry/_core.py src/aeat/core/errors/test_registry.py`
- `uv run pytest src/aeat/core/observability/test_context_propagation.py src/aeat/core/observability/test_sink.py src/aeat/core/observability/test_models.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q`
- `uv run python -m aeat.locales audit`

## Safety Notes

- No deprecated config-init command surface was introduced.
- No `pragma` or `noqa` suppression was added; one stale pragma on the touched context cleanup path was removed.
- New tests use real filesystem states and do not add fake, stub, monkeypatch, skip, xfail, or mirrored business logic patterns.
- The new user-facing error registry message was added through `python -m aeat.locales`.
