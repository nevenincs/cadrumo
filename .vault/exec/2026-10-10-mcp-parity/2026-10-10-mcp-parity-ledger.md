---
tags:
  - '#exec'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:f6f5b6e58f35859ff82f6f79327623279d4462f36c589707cf540f60246cfc8b'
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

## Notes

- `S08` The subject-reference form could not be stated from inside the harness and moved to its own Step. One existing result-page test was already failing at HEAD on a stale page-size literal and is corrected here.
