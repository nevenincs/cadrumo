---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S244]]'
---

# `secure-storage-production-hardening` Code Review

## S244-001 | FIXED | Overview row was misclassified as remote-mirror

`src/aeat/application/overview/__init__.py` has no remote provider call and the CLI overview help states the verbs are local-only. The status path reads persisted state by delegating to the canonical `build_operator_state_projection`, which is runtime-backed and secure-object enrolled. The correct affected-file target is therefore `runtime-default`, not `remote-mirror` or `manifest-discovery`.

## S244-002 | FIXED | Intentional degradation paths now leave non-secret debug evidence

The calendar path still degrades benign no-deadline-window years and missing holiday-shift calendars, but it now logs debug records with bounded metadata (`year`, `modelo`, `period`, `error_type`) instead of silently swallowing the condition. Genuine registry-integrity faults continue to propagate.

Invalid filing-obligation profile inputs now log field-name and error-shape metadata at debug level, without raw values. The advisory still returns no filing-obligation hint when the input is invalid.

## S244-003 | FIXED | Central decimal coercion no longer logs raw malformed values

`src/aeat/core/decimal/_coerce.py` previously logged the malformed value and default with `%r` on parse failure. That could leak operator profile or spreadsheet data at debug level. The helper now logs only `value_type`, `default_is_none`, and `error_type`, preserving centralized decimal coercion while removing raw-value exposure.

## S244-004 | FIXED | Unused raw overview status renderer removed

The application package exported an unused `render_overview_status_lines` helper that emitted raw `profile_id` text. The live CLI uses `entrypoints.cli._overview_rendering.render_cli_overview_status_lines` through `_emit_envelope`, which routes text and JSON through the centralized output redaction layer. Removing the unused helper reduces accidental bypass surface.

## S244-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/core/decimal/_coerce.py src/aeat/core/decimal/test_coerce.py src/aeat/application/overview/__init__.py src/aeat/application/overview/test_calendar.py src/aeat/entrypoints/cli/test_overview_rendering.py src/aeat/entrypoints/cli/test_overview_verbs.py` passed.
- `uv run --no-sync pytest -q src/aeat/core/decimal/test_coerce.py src/aeat/application/overview/test_calendar.py src/aeat/entrypoints/cli/test_overview_rendering.py src/aeat/entrypoints/cli/test_overview_verbs.py` passed with 109 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca`, `en`, `es`, and `hu`.

Disposition: close `AFR-142` as `runtime-default`.
