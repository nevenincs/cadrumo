---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:f183e39aa73b0288c3bd6591c3bad49c9850009a84460173081057e379ecb58c'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S151` Review

## S151-001 | PASS | Rotation remains a bounded plaintext exception

The helper walks file paths and rewrites encrypted envelope bytes under a new master key. It continues not to parse typed payload schemas or persist plaintext business payloads. Per-file atomic replacement and lock alignment remain intact.

## S151-002 | PASS | Rotation logs no longer emit full paths on primary failure paths

Before S151, parse/decrypt/encrypt/write rotation logs passed the full `Path` object to `_log.warning()` / `_log.error()` / `_log.debug()`. The central logging filter redacts sensitive shapes but does not classify every arbitrary filesystem path as secret, so profile roots and record path segments could appear in diagnostic output.

Resolution: `_path_log_marker()` derives a stable SHA-256 marker from the resolved path and logs that marker instead of the path. Path-bearing `exc_info=True` was removed from those failure logs to avoid exception text reintroducing the path.

## S151-003 | PASS | Tests exercise real rotation behavior

The added warning test creates a real malformed envelope file under a private-looking directory, runs `rotate_master_key()`, captures the real logger output, and asserts the marker appears while the private path segment and full target path do not.

Validation:

- The historical check passed with 24 tests.
- The historical check passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Case-sensitive touched-file hygiene scan found no broad exception catches, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, direct output, raw UTF-8 literals, or local `Path("db://secure_objects")` construction.
- Subagent reviewer James reported no findings. Residual scope note: the path marker is unsalted truncated SHA-256, so it is linkable and guessable by an actor who already knows likely path candidates; S151 treats it as a diagnostic marker, not a keyed privacy token.

Disposition: close `AFR-049` as `plaintext-exception`.
