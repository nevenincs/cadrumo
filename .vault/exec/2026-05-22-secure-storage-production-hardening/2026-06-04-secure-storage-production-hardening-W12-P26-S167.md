---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S167'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S167-review]]'
---

# `secure-storage-production-hardening` `W12.P26.S167`

Closed `AFR-065` for the file-backed envelope implementation.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/envelope/_envelope.py` against the `master-key` and `plain-file` scanner signals.
- Confirmed plaintext envelope persistence is an explicit `plaintext-exception` substrate path with schema version, classification, and migrator gates.
- Confirmed encrypted envelope persistence derives per-consumer AEAD keys from the supplied master-key provider and binds classification plus HKDF context into AAD.
- Wrapped envelope read, parse, write, base64 metadata, and decrypted-inner-JSON failures in AEAT storage exceptions.
- Removed filesystem paths from envelope classification, version, AAD, and corrupted-inner-envelope messages.
- Added real filesystem and persisted-metadata tamper coverage for the new exception/redaction behavior.
- Closed `S167` through `vaultspec-core vault plan step check` and updated `AFR-065` to closed.

## Outcome

`AFR-065` is closed as a reviewed `plaintext-exception` implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/envelope/_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope.py src/aeat/adapters/persistence/storage/envelope/test_envelope_ciphertext.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` with the known `PLAN022` ordering warning.
- `uv run --no-sync vaultspec-core vault check links` with existing stem-collision warnings.
- Touched-surface hygiene scan found no broad exception catches, unlogged suppressions, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, local secure-object marker construction, direct settings construction, or direct environment access.

Validation exception:

- `uv run --no-sync -q python -m aeat.locales audit` failed on pre-existing `cli.config.init.*` missing keys in `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`; this row did not add or edit locale strings.
- `uv run --no-sync vaultspec-core vault check body-links` and `uv run --no-sync vaultspec-core vault check dangling` failed on existing vault-wide unrelated records; this row's audit and exec documents contain wiki-links only in `related:` frontmatter.

## Notes

The `save_envelope` plaintext path remains intentional substrate behavior for non-sensitive file-backed records and migrations. Sensitive repository payloads remain covered by the encrypted envelope APIs and secure repository rows. The new modelo export evidence and workbook parity ADR constraints remain applicable to later export rows; this row only governs local envelope file I/O.
