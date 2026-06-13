---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S04'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# W01.P02.S04 - Central live-read and live-write gate proof

Scope: prove live reads route through the central gate and live writes refuse before transport construction.

## Description

- Inspect the central access gate and live session helper.
- Inspect live backend call sites for `active_verified_session` and direct `AeatAccessGate.require_live_read` usage.
- Run the central auth gate tests and the focused live safety tests.

## Outcome

`AeatAccessGate.require_live_read` remains the central pytest opt-in guard for live AEAT reads. Operator CLI reads are still allowed to proceed to authentication/profile/read-only guards outside pytest, while pytest-driven live reads require the literal `AEAT_LIVE_TESTS_ENABLED=1` value.

`active_verified_session` loads validated settings, calls `AeatAccessGate(settings).require_live_read()`, then acquires an authenticated AEAT session. The live backend surfaces inspected route through that helper or call the access gate directly for verify and IVA remote acquisition paths.

`AeatAccessGate.require_live_write` is unconditional and raises `LiveSubmitForbiddenError` without reading settings or constructing transport. Export error tests also alias the outbound export refusal to the central core error.

## Verification

- `Get-Content -Raw src/aeat/core/access_gate/__init__.py` confirmed read and write gate semantics.
- `Get-Content -Raw src/aeat/application/live/_session.py` confirmed `active_verified_session` calls `require_live_read` before authentication.
- `rg -n "active_verified_session\\(|require_live_read\\(|require_live_write\\(|LiveSubmitForbiddenError|submit\\(|push\\(|acknowledge\\(|dismiss\\(" src/aeat/application/live src/aeat/adapters/outbound/aeat src/aeat/entrypoints/cli -g "*.py"` identified live read gate call sites and no production live submit/acknowledge/dismiss methods.
- `uv run pytest src/aeat/adapters/outbound/aeat/auth/tests/test_gate.py src/aeat/domain/calculations/registry/tests/test_remote_state_guard.py src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_pull_help_locale_keys_do_not_use_capture_all_names src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestReadOnlyStructuralInvariants::test_no_submit_send_or_present_verb_exists -q` passed with 52 selected tests.

## Notes

This row proves the central gate and permanent write refusal. It does not prove authenticated AEAT credentials are available for the later manual live rows.
