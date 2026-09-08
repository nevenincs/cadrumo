---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:276c43085e95e4acdfcc52ebaa82957b04de60bc7b2399667561ca80f322f8b5'
step_id: 'S213'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Amend the accepted Workspace API decision so the live eight producer contracts remain canonical while production no longer carries a conformance-only aggregate inventory; delete ModeloWorkspaceProducerContractInventoryV1, MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1, their exports and inventory-only tests, and rewrite the native-owner fixed-point gate to derive its set directly from live port contracts without a hand-maintained production list.

## Scope

- `Workspace producer contracts and conformance tests`
- `governing Workspace API ADR`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S213.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `rg -n "ModeloWorkspaceProducerContractInventoryV1|MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1|producer_contract_inventory_digest" src dev --glob '*.py'` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 63 unreachable modules, 313 exact unused symbols, 15 orphaned tests, 2028/2092 shipped modules reachable)`
