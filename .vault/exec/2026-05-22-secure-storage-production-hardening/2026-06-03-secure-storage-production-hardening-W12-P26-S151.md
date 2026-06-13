---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S151'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s151-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S151`

Closed `AFR-049` for the master-key rotation helper.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/_rotation.py` against the `master-key` and `plain-file` scanner signals.
- Kept rotation classified as a `plaintext-exception`: it traverses and rewrites encrypted envelope files and blob manifests but does not parse or persist plaintext business payloads.
- Added a stable `_path_log_marker()` helper so rotation warning/error logs can correlate a failing file without emitting the full filesystem path.
- Replaced full-path warning/error/debug log arguments on envelope parse, already-rotated, decrypt, encrypt, and atomic-write paths with path markers plus error type.
- Removed `exc_info=True` on path-bearing rotation failure logs where exception text could repeat filesystem paths.
- Replaced raw UTF-8 literals in rotation tests with `UTF_8_ENCODING`.
- Added real log-capture coverage proving malformed-envelope warnings include a marker and omit the private path segment/full path.
- Closed `W12.P26.S151` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-049` is closed as `plaintext-exception`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_rotation.py -k "rotation or rotate or malformed_envelope_warning"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_rotation.py src/aeat/adapters/persistence/storage/test_rotation.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, or local `Path("db://secure_objects")` construction.

## Notes

The central logging filter remains the project-wide redaction authority, but it does not treat every arbitrary filesystem path as a secret. Rotation now avoids sending those paths to the logger in the first place on its own failure/progress paths.
