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



# Deadline, manual, and normative plaintext-exception closeout audit

## Scope

This closeout covers W12.P26.S335, S336, S337, S346, S349, S350, S351, and S360.

## Findings

- Deadline calendar and recargo modules read public BOE-grounded registry files only; they do not own mutable profile, ledger, filing, session, or secret storage.
- Malformed recargo registry data now remains fatal instead of being downgraded to a missing recovery payload. Benign recovery absence still logs a debug breadcrumb before returning no recovery.
- Deadline calendar and recargo file/parsing failures are wrapped in `DeadlineValidationError`.
- IVA recargo-equivalencia registry-loader failures are wrapped into the IVA exception family.
- Manual fetch/loader/verify now wrap manifest, PDF, and structure-file I/O failures into manual-domain errors. Manual verification messages route through `tr()` keys added via `python -m aeat.locales`.
- Normative loader stat/read/schema failures remain in the normatives exception family with diagnostic logging for read and validation failures.

## Closeout Rationale

These plaintext reads and writes are accepted only for public authority artefacts and diagnostic/manual manifests. They are not alternate secure-object stores and must not be used for profile aggregates, user sessions, filing records, ledger data, or remote mirror payloads.

## Validation

- `uv run ruff check src/aeat/domain/deadlines/_engine.py src/aeat/domain/deadlines/_festivos.py src/aeat/domain/deadlines/_recargo.py src/aeat/domain/deadlines/test_recargo.py src/aeat/domain/deadlines/test_festivos.py src/aeat/domain/iva/_recargo_equivalencia.py src/aeat/domain/iva/test_legal_basis_binding.py src/aeat/domain/manuals/_fetch.py src/aeat/domain/manuals/_loader.py src/aeat/domain/manuals/_verify.py src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_verify.py src/aeat/domain/normatives/_loader.py src/aeat/domain/normatives/test_loader.py`
- `uv run pytest src/aeat/domain/deadlines/test_recargo.py src/aeat/domain/deadlines/test_festivos.py src/aeat/domain/iva/test_legal_basis_binding.py src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_verify.py src/aeat/domain/normatives/test_loader.py -q`
- `uv run python -m aeat.locales audit`
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Safety Notes

- Locale additions were performed through `python -m aeat.locales set`.
- No deprecated config-init command surface was introduced.
- No `pragma` or `noqa` suppression was added.
- No test was added that uses fake, stub, monkeypatch, skip, xfail, or mirrored business logic.
