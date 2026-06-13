---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S38'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
  - '[[2026-06-10-cli-operator-surface-adr]]'
---

# W03.P07.S38 - profile-history retired-bucket tests and gates

## Scope

- `src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py`
- `src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`
- `dev/docs/tests/test_cli_reference_conformance.py`

## Description

- Added a help-shape test asserting `config profile history --help` exposes `PROFILE` and not `BUCKET_ID`.
- Extended the real subprocess profile-selection test so event-history reads use profile labels and text output does not expose raw `bucket_id` rows.
- Updated CLI-reference conformance to honour the deliberate `config.profile.history` to `config.bucket.history` stable-token override and the existing `ledger.participation` group-callback schema.

## Outcome

Focused real-behavior tests and conformance gates pass. The retired `config bucket` group stays unknown, the live history verb is under `config profile`, and the D5/documented-command/schema gates remain green for this slice.

## Notes

Verification:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py::test_profile_history_help_exposes_profile_argument_not_bucket_id -m "unit or integration" -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py::test_profile_selection_precedence_uses_explicit_env_then_pointer -m "unit or integration" -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m "unit or integration" -q`
- `uv run --no-sync pytest dev/docs/tests/test_cli_reference_conformance.py -m "unit or integration or hex_core" -q`
- `uv run --no-sync pytest dev/docs/tests/test_cli_reference_drift.py -m "unit or integration or hex_core" -q`
