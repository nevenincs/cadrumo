---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d3387ab9daaa7f7332f420b6f46e03584001e8f01782874ea82e1717a1ac846f'
step_id: 'S116'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# Repair the locale-dependent assertions the axis surfaces, replacing each with the stable transport token it stood for or with an explicit locale pin, and reporting a removed redundant branch as a strengthening rather than a defect fixed (Terra xhigh fixes and refactors)

## Scope

- `src/cadrumo/`

## Changes

- Added explicit declared English pinning to four helpers or invocations whose assertions intentionally inspect English transport copy.
- Redirected three localized negative checks from normalized display text to the pinned raw CLI result.
- Replaced the Spanish `presentado` absence check with the stable structured refusal code.
- Removed eight redundant localized negative assertions after stronger exit-code, structured-envelope, canonical-token, or positive-content assertions had already established the intended behavior.
- Added the declared output-language environment pin to the first-run CLI test environment. The adjacent unsupported-provider rename in that file is unrelated and is excluded from this Step's staged patch.

## Measured repair set

A differential census ran the locale detector over each modified test module twice: once against `HEAD` bytes and once against current working-tree bytes, under both English and Spanish ambient axes. Exactly 12 files changed detector behavior. Their committed bytes produced 16 findings; their working-tree bytes produced zero.

The 12 repaired files are:

- `src/cadrumo/application/user_profile/tests/test_first_run_config_cli_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_config_storage_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_filing_refuses_undeclared_tax_id.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_202_required_binding_gate.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_casilla_canonical_ids.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_discovery_defects.py`
- `src/cadrumo/entrypoints/cli/tests/test_modelo_unsupported_work_refusal.py`
- `src/cadrumo/entrypoints/cli/tests/test_overview_explain_verb.py`
- `src/cadrumo/entrypoints/cli/tests/test_participation_cli_surface.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_output_language.py`
- `src/cadrumo/entrypoints/cli/tests/test_registry_cli.py`

## Verification

- `uv run pytest dev/quality/tests/test_locale_bound_assertions.py -q -m "" -n 0` -> `63 passed in 45.56s`; the real-tree English and Spanish sweeps are empty.
- Differential committed/current census -> `16` findings before, `0` after, across exactly the 12 files above.
- Exact affected-node run -> `16 passed, 4 failed`. The four failures are not counted as repair verification: each stopped before its changed assertion due to adjacent registry/readiness/profile-session behavior. They were `test_laura_m202_not_ready_refuses_calculate_and_no_zero_artifact_is_reachable`, `test_qualified_casilla_key_passes_validation_unchanged`, `test_describe_m210_accepts_numbered_event_token_with_year_scope`, and `test_config_profile_view_inspects_a_tombstoned_profile_by_label_and_uuid`.
- Broad 12-module run -> `98 passed, 28 failed, 25 errors`; failures and setup errors are adjacent current-tree behavior, including strict tuple validation in registry inspection and changed readiness/session preconditions. This result is recorded, not repaired or presented as green.

## Disposition

These changes strengthen assertion stability and precision; they do not claim product defects were fixed. Locale copy is asserted only when the test explicitly pins that locale. Otherwise the test uses stable transport structure or removes a redundant negative whose intended condition is already proved directly.
