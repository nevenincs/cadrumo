---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S167'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s167-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S167`

Closed `AFR-065` for the file-backed envelope implementation.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/envelope/_envelope.py` against the `master-key` and `plain-file` scanner signals.
- Confirmed plaintext envelope persistence is an explicit `plaintext-exception` substrate path with schema version, classification, and migrator gates.
- Confirmed encrypted envelope persistence derives per-consumer AEAD keys from the supplied master-key provider and binds classification plus HKDF context into AAD.
- Wrapped envelope read, parse, write, base64 metadata, and decrypted-inner-JSON failures in AEAT storage exceptions.
- Removed filesystem paths from envelope classification, version, AAD, and corrupted-inner-envelope messages.
- Routed envelope implementation and direct tests through `UTF_8_ENCODING` instead of direct encoding literals.
- Replaced the generic envelope factory `type: ignore` with an explicit `cast` and retained the local rationale comment.
- Added real filesystem and persisted-metadata tamper coverage for the new exception/redaction behavior.
- Closed `S167` through `vaultspec-core vault plan step check` and updated `AFR-065` to closed.

## Outcome

`AFR-065` is closed as a reviewed `plaintext-exception` implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/envelope/_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` with the known `PLAN022` ordering warning.
- Touched-surface hygiene scan found no broad exception catches, suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, direct encoding literals, pragma/noqa/type-ignore directives, local secure-object marker construction, direct settings construction, or direct environment access.

## Notes

The `save_envelope` plaintext path remains intentional substrate behavior for non-sensitive file-backed records and migrations. Sensitive repository payloads remain covered by the encrypted envelope APIs and secure repository rows. The new modelo export evidence and workbook parity ADR constraints remain applicable to later export rows; this row only governs local envelope file I/O.
