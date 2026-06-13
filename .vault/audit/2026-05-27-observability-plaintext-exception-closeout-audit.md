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



# Observability plaintext-exception closeout audit

## Scope

This closeout covers W12.P26.S303, W12.P26.S304, and W12.P26.S307.

| Row | AFR | Module | Disposition |
| --- | --- | --- | --- |
| W12.P26.S303 | AFR-201 | `observability._errors` | accepted plaintext exception |
| W12.P26.S304 | AFR-202 | `observability._fingerprint` | accepted plaintext exception |
| W12.P26.S307 | AFR-205 | `observability._sink` | accepted plaintext exception |

## Findings

- `observability._errors` is exception taxonomy only. Its concrete exceptions derive from the core AEAT exception hierarchy and are registered in the central error registry.
- `observability._fingerprint` reads architecture, runtime, and certificate paths to compute deterministic drift hashes. It does not persist user data. Unreadable files remain represented by a deterministic sentinel, and the root cause is now logged at debug level before the sentinel is used.
- `observability._sink` writes diagnostic JSONL run events. The sink redacts structured diagnostic payloads before serialization, filters by run id, flushes every event, and fsyncs on close. Its broad `emit` catch follows the stdlib logging handler contract and logs with `exc_info=True` before calling `handleError`.

## Closeout Rationale

These surfaces are not alternate secure-object stores. They are diagnostic boundary code:

- exception types,
- drift fingerprints,
- redacted run-event emission.

They may touch plaintext filesystem paths because observability must inspect and report runtime state, but they do not own profile aggregates, model work units, ledger data, filing records, session secrets, or remote mirror payloads. The retained plaintext disposition is therefore bounded to diagnostics and is not a storage API bypass.

## Validation

- `uv run ruff check src/aeat/core/observability/_errors.py src/aeat/core/observability/_fingerprint.py src/aeat/core/observability/_sink.py src/aeat/core/observability/test_replay.py src/aeat/core/observability/test_sink.py src/aeat/core/observability/test_sink_redaction.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py`
- `uv run pytest src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/core/observability/test_replay.py src/aeat/core/observability/test_sink.py src/aeat/core/observability/test_sink_redaction.py -q`

## Safety Notes

- No deprecated config-init command surface was introduced.
- No `pragma` or `noqa` suppression was added.
- No test was added that uses fake, stub, monkeypatch, skip, xfail, or mirrored business logic.
- No exception swallowing was retained without logging; the unreadable-file fingerprint branch now records a debug-level breadcrumb.
