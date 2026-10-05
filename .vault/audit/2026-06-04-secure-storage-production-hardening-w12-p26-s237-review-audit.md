---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:40c34cb76e443540131fa67401610345113f8b997522f97e2010ac5dac0de739'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S237` Review

## S237-001 | PASS | History is a read-only assembly surface

`assemble_work_unit_history()` loads work units, calculation revisions, filing
records, verification reports, and bucket events through their repository
interfaces, then returns an in-memory chronological projection. The module does
not own a storage namespace, plaintext file path, SQL route, environment
override, remote provider, or mutation verb.

## S237-002 | PASS | Storage ownership remains in runtime repositories

The storage decisions for the data this assembler reads live in the underlying
domain repositories: work units, calculation revisions, filing records,
verification reports, and bucket events. S237 therefore closes as
`manifest-discovery` rather than `runtime-default` or `remote-mirror`.

## S237-003 | PASS | Missing work-unit refusal is locale-backed

The missing-work-unit path now raises `WorkUnitNotFoundError` with
`application.modelo.errors.work_unit_not_found` and structured context. This
aligns `_history.py` with the existing `_actions.py` work-unit lookup
convention instead of emitting a raw id-specific string.

## S237-004 | PASS | Validation

- the historical check passed.
- the historical check passed with 7 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-135` as `manifest-discovery`.
