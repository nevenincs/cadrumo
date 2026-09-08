---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:13f4a4918f81da90131552d1b1ba20b981e1e200c867c3f2dab8f0d6489c324b'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# `quality-gate-zero-closure` `W08.P25` summary

## Changes

- `A` `dev/quality/locale_bound_assertions.py`
- `A` `dev/quality/tests/fixtures/locale_axis_blind.py.fixture`
- `A` `dev/quality/tests/fixtures/locale_bound_assertions.fixture`
- `A` `dev/quality/tests/test_locale_bound_assertions.py`
- `M` `src/cadrumo/application/user_profile/tests/test_first_run_config_cli_surface.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_filing_refuses_undeclared_tax_id.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_202_required_binding_gate.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_casilla_canonical_ids.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_discovery_defects.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_unsupported_work_refusal.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_output_language.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_registry_cli.py`
- `verify:` `uv run pytest dev/quality/tests/test_locale_bound_assertions.py -q -m "" -n 0` -> `pass` (`63 passed`)
- `verify:` external `/tmp` bounded `mutmut run "dev.quality.locale_bound_assertions*"` -> `pass` (`475 selected; 452 killed; 23 inert survivors; 597.38 s`)

## Notes

The complete pre-repair four-catalogue sweep failed in both parameterized directions: Spanish exposed seven English-only absence sites and English exposed one Spanish-only site. The runtime axis maps each hit to its pytest node, clears the repository default marker, and executes it under both locales; isolated and integration-marked positive controls prove both branches bite. After S116, the current hit set is empty. A fresh affected-node run reached 12 passes and four failures that stopped before the assertions changed by this campaign; those four are not claimed as behavioral passes. All behavior-changing locale mutants were killed and each of the 23 survivors was individually closed as semantically inert.
