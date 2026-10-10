---
tags:
  - '#exec'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:ee00ddd4047900a3d0f3f5c12b99f9cddb79e43af2a041d5f2bc53e8d32fd842'
related:
  - "[[2026-10-10-mcp-parity-plan]]"
---

# `mcp-parity` ledger

## Changes

- `S10` `M` `src/cadrumo_harness/_data/agent/README.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-classifier.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-coordinator.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-ledger-groomer.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-modelo-preparer.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-onboarding.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-reconciler.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/personas/cadrumo-verifier.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-lifecycle-ordering.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-safety-handoff.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-alta-contribuyente/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-exportar-declaracion/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-llevar-libro/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-100/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-111/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-115/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-130/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-131/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-180/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-190/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-193/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-200/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-202/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-303/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-309/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-322/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-349/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-353/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-369/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-preparar-modelo-390/SKILL.md`
- `S10` `M` `src/cadrumo_harness/_data/agent/skills/cadrumo-rectificar-declaracion/SKILL.md`
- `S10` `verify:` `pytest dev/agent_eval/tests/test_rule_surface_conformance.py -n0 -m "unit or integration"` -> `pass`
- `S10` `verify:` `pytest src/cadrumo_harness/tests/test_skill_applies_when.py src/cadrumo_harness/tests/test_harness_data_ships.py -n0 -m "unit or integration"` -> `pass`
- `S10` `by:` `vaultspec-standard-executor`
- `S04` `M` `src/cadrumo/application/user_profile/automation_operations.py`
- `S04` `M` `src/cadrumo/application/export/google_operation.py`
- `S04` `M` `src/cadrumo/application/local_reader_operation.py`
- `S04` `M` `src/cadrumo/application/user_profile/operations.py`
- `S04` `M` `src/cadrumo/application/user_profile/tests/test_automation_inventory_operation.py`
- `S04` `M` `src/cadrumo/application/user_profile/tests/test_bundle_export_access.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/tests/test_google_operation.py`
- `S04` `M` `src/cadrumo/adapters/persistence/operations/tests/test_local_reader_operation.py`
- `S04` `M` `docs/technical/articles/027-local-reader-provisioning-workstation-health-and-application-contracts.md`
- `S04` `verify:` `pytest (13 covering test files) -n0 -m "(unit or integration) and not perf ..."` -> `pass`
- `S04` `verify:` `ruff check` -> `pass`
- `S04` `verify:` `ruff format --check` -> `pass`
- `S04` `verify:` `ty check --python-platform linux` -> `pass`
- `S04` `verify:` `registry dump before and after: exactly seven definitions lost MCP` -> `pass`
- `S04` `by:` `vaultspec-standard-executor`
- `S08` `M` `src/cadrumo_harness/mcp/admitted_operations.py`
- `S08` `M` `src/cadrumo_harness/mcp/protocol_contract.py`
- `S08` `M` `src/cadrumo_harness/mcp/runtime_adapter.py`
- `S08` `M` `src/cadrumo_harness/mcp/tests/test_operation_search_tool.py`
- `S08` `M` `src/cadrumo_harness/mcp/tests/test_result_page_tool.py`
- `S08` `A` `src/cadrumo_harness/mcp/operation_contract_cache.py`
- `S08` `A` `src/cadrumo_harness/mcp/operation_discovery.py`
- `S08` `A` `src/cadrumo_harness/mcp/result_request.py`
- `S08` `verify:` `pytest src/cadrumo_harness/mcp/tests src/cadrumo_harness/tests -n0 (188 tests)` -> `pass`
- `S08` `verify:` `ruff check` -> `pass`
- `S08` `verify:` `ruff format --check` -> `pass`
- `S08` `verify:` `ty check --python-platform linux` -> `pass`
- `S08` `by:` `vaultspec-standard-executor`
- `S08` `M` `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md`
- `S08` `verify:` `pytest dev/agent_eval/tests/test_rule_surface_conformance.py and harness data tests -n0 (14 tests)` -> `pass`
- `S01` `A` `src/cadrumo/application/operations/mcp_admission.py`
- `S01` `A` `src/cadrumo/entrypoints/tests/test_operation_mcp_admission.py`
- `S01` `A` `src/cadrumo/application/operations/tests/test_mcp_admission.py`
- `S01` `verify:` `pytest test_operation_mcp_admission.py test_mcp_admission.py test_operation_catalogue.py -n0 (47 tests)` -> `pass`
- `S01` `verify:` `ruff check` -> `pass`
- `S01` `verify:` `ruff format --check` -> `pass`
- `S01` `verify:` `ty check --python-platform linux` -> `pass`
- `S01` `verify:` `basedpyright and pyrefly on mcp_admission.py` -> `pass`
- `S01` `verify:` `just check-import-boundaries` -> `fail`
- `S01` `by:` `vaultspec-high-executor`
- `S07` `A` `src/cadrumo/core/path_confinement.py`
- `S07` `A` `src/cadrumo/core/tests/test_path_confinement.py`
- `S07` `M` `src/cadrumo/application/modelo/reconciliation_import_operation.py`
- `S07` `M` `src/cadrumo/application/live/filed_history_operation.py`
- `S07` `M` `src/cadrumo/application/live/filed_single_capture_operation.py`
- `S07` `M` `src/cadrumo/application/live/filed_bulk_capture_operation.py`
- `S07` `M` `src/cadrumo/application/live/filed_source_capture_operation.py`
- `S07` `M` `src/cadrumo/application/live/iva_wallet_history_capture_operation.py`
- `S07` `M` `src/cadrumo/application/live/iva_remote_state_capture_operation.py`
- `S07` `M` `src/cadrumo/application/live/tests/test_provider_capture_preparation.py`
- `S07` `M` `src/cadrumo/entrypoints/tests/test_modelo_reconciliation_import_operation.py`
- `S07` `M` `.vault/reference/2026-10-10-mcp-parity-admitted-surface-defects-reference.md`
- `S07` `verify:` `pytest test_path_confinement.py test_provider_capture_preparation.py test_modelo_reconciliation_import_operation.py -n0 (36 tests)` -> `pass`
- `S07` `verify:` `pytest test_registered_executor_conformance.py -k reconcile/filed/iva-wallet (20 tests)` -> `pass`
- `S07` `verify:` `pytest src/cadrumo/application/live/tests -k capture/filed/wallet (117 tests)` -> `pass`
- `S07` `verify:` `ruff check` -> `pass`
- `S07` `verify:` `ruff format --check` -> `pass`
- `S07` `verify:` `ty check --python-platform linux` -> `pass`
- `S07` `by:` `vaultspec-high-executor`
- `S15` `M` `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py`
- `S15` `A` `src/cadrumo/adapters/persistence/storage/master_key/tests/test_profile_worker_custody_lease_window.py`
- `S15` `M` `.vault/reference/2026-10-10-mcp-parity-sign-in-doors-reference.md`
- `S15` `verify:` `pytest test_profile_worker_custody_lease_window.py -n0 (4 tests)` -> `pass`
- `S15` `verify:` `pytest master_key neighbours: bucket session, absolute cap, idle timeout, worker binding (45 tests)` -> `pass`
- `S15` `verify:` `pytest runtime: lease retirement, human login receipt, worker settlement (12 tests)` -> `pass`
- `S15` `verify:` `ruff check` -> `pass`
- `S15` `verify:` `ruff format --check` -> `pass`
- `S15` `verify:` `ty check --python-platform linux` -> `pass`
- `S15` `by:` `vaultspec-high-executor`

## Notes

- `S08` The subject-reference form could not be stated from inside the harness and moved to its own Step. One existing result-page test was already failing at HEAD on a stale page-size literal and is corrected here.
- `S01` The import-boundary gate fails for reasons outside this Step: two private cross-package findings under dev/packaging and a stale generated module inventory; all 15 contracts are kept and no chain involves these files. The inventory entries for the new modules are regenerated in a separate commit. Twelve MCP-listed operations are not proven through their real resolver and are pinned in a named set; the no-submission assertion covers what operations, tools and commands declare and cannot see executor or adapter behaviour.
- `S07` Not delivered here and carried to the file-exchange Step: root confinement of the reconciliation import, for want of any existing setting, and a bytes entry for the declaracion parser, which is still parsed by path between two verified reads. The POSIX branch of the guard has not executed; tests ran on Windows only. The strict checkers were not run on these files with a working invocation.
- `S15` Still reachable and not introduced here: a key read after the latest lease expiry and before the custody poll closes the session; a retire that finds no session when two root leases are still listed at that moment; and a lease installed or refreshed while a section is held, which is not covered until the last section exits. The worker can refresh only key leases, so extending a sign-in will need a way to move a human lease deadline. Tests do not cover held sections or the real worker loop.
