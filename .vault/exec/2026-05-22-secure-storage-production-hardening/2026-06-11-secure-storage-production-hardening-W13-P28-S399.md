---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S399'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-06-secure-storage-production-hardening-W13-P27-S398]]'
  - '[[2026-06-06-secure-storage-production-hardening-w13-p27-s397-persona-finding-requirements-research]]'
---

# W13.P28.S399 secure-storage persona retests

Scope: execute `W13.P28.S399` from the secure-storage production hardening plan.

## Description

- Re-ground S399 against the current shared worktree after backend and CLI changes landed.
- Dispatch focused retests for the secure-storage-owned testimonial findings: FRESH-011 unreadable stored-draft readiness and REPAIR-PROFILE-PRIVACY-001 repair-profile privacy.
- Run existing real CLI and backend tests with isolated storage fixtures rather than new fakes, monkeypatches, or ad hoc environment mutation.
- Record sidecar persona dispatch failure: two read-only persona agents were requested for Bruno and Elena retest slices, but the multi-agent runtime returned usage-limit errors before execution. The retest was completed locally through the same focused commands.

## Outcome

Current S399 retests pass:

- `uv run --no-sync pytest -m "integration or hex_entrypoint" src/aeat/entrypoints/cli/tests/test_modelo_discovery_defects.py::test_modelo_readiness_names_preflight_scope -q` passed.
- `uv run --no-sync pytest -m "integration or hex_entrypoint" src/aeat/entrypoints/cli/tests/test_repair_privacy_contract.py::test_config_repair_profile_cli_redacts_profile_identifiers src/aeat/entrypoints/cli/tests/test_repair_privacy_contract.py::test_config_repair_integrity_objects_cli_is_metadata_only_for_unreadable_rows src/aeat/entrypoints/cli/tests/test_repair_privacy_contract.py::test_config_repair_quarantine_dry_run_is_metadata_only_and_non_mutating -q` passed.
- `uv run --no-sync pytest src/aeat/application/tests/test_repair_integrity.py::TestBuildIntegrityReport::test_undecryptable_rows_surface_fail_with_next_action src/aeat/application/tests/test_repair_integrity.py::TestBuildListReport::test_list_unreadable_filters_to_only_failed_decryption_rows -q` passed.
- `uv run --no-sync pytest -m "integration or hex_entrypoint" src/aeat/entrypoints/cli/tests/test_repair_bootstrap_exempt.py::test_repair_verb_runs_clean_without_session_on_fresh_root -q` passed.

The first current-tree S399 run exposed two active blockers before the focused fixes in the shared tree were present: `modelo readiness` rejected raw period strings after the centralized `Period` rollout, and `config repair integrity objects` failed Pydantic forward-reference rebuilding for `SecureObjectNamespaceIntegrity`. The current focused rerun proves the S399 surfaces now pass.

## Notes

No new secure-storage repair row is justified by S399 evidence. A broader direct application state-projection probe still fails on the already-documented wizard profile-key registration harness issue recorded by the period-grammar standardisation execution record; that is not a secure-storage-owned S399 blocker because the CLI readiness and repair surfaces under S399 pass with isolated real fixtures.
