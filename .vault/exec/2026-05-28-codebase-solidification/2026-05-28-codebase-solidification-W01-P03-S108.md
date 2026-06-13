---
step_id: S108
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S108 — describe BadParameter localization tests

## Outcome

Added two real-behavior tests to `src/aeat/entrypoints/cli/test_modelo.py`:

- `test_describe_non_period_error_is_localized`: invokes `describe 999` via real CLI
  runner, confirms no Traceback, and calls `tr("cli.app.modelo.describe.period_error", ...)`
  directly to verify the key resolves to a non-empty string.
- `test_describe_period_error_locale_key_interpolates_message`: passes a sentinel value
  as `message` kwarg and asserts it appears in the rendered output — proving the
  `%{message}` slot is wired.

Also fixed a pre-existing test regression: `test_describe_surfaces_revision_ids_for_work_create`
was asserting the literal string `"Revision ids"` but the WIP locale changes resolved
`label_revision_ids` to `"Label revision ids"`. Updated assertion to `"revision" in lower`.

Fixed `test_work_calculate_binding_help_points_at_bindings_list`: the CliRunner renders
Rich box-drawing characters that split the long `--binding` help text. Added ASCII-only
filter + whitespace collapse before asserting the phrase.

## Files touched

- `src/aeat/entrypoints/cli/test_modelo.py`

## Verification

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py -q` → 142 passed,
3 pre-existing failures (filing_record_payload, period_token_error_enumerates, filing_record_omits).
New tests: all 4 pass.
