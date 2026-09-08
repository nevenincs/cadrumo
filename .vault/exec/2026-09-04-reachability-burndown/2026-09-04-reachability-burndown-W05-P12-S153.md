---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:1805ee9f43831bce29d970eb8139dcebba7fa8e0cf4c2fd68276d14953f414db'
step_id: 'S153'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the test-only IVA wallet URL alias, migrate tests to the canonical parsing authority, and strengthen the public-alias detector to catch imported-target aliases without identity exceptions.

## Scope

- `IVA wallet URL authority`
- `dependent tests`
- `test-only public-alias quality gate`

## Changes

- `M` `dev/quality/tests/test_no_test_only_public_alias.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/iva_compensation_wallet.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_landed_origin_refusal.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_observation_store_namespace_binding.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_observation_store_roundtrip.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_observation_store_row_identity.py`
- `M` `src/cadrumo/application/aggregation/tests/test_source_mesh_profile_live.py`
- `M` `src/cadrumo/application/calculations/tests/_iva_compensation_history_support.py`
- `M` `src/cadrumo/application/calculations/tests/test_iva_wallet_reconciliation.py`
- `M` `src/cadrumo/application/live/tests/test_iva_wallet_capture_backend.py`
- `M` `src/cadrumo/application/modelo/tests/_iva_wallet_engine_support.py`
- `M` `src/cadrumo/application/modelo/calculation_source_policy.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/tests/test_operator_override_advisory.py`
- `M` `src/cadrumo/application/modelo/tests/test_source_mesh_missing_sources.py`
- `M` `src/cadrumo/application/modelo/tests/test_unrouted_source_refusal.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 dev/quality/tests/test_no_test_only_public_alias.py` -> `pass`
- `verify:` `uv run ruff check ...` -> `pass`
- `verify:` `rg -n "IVA_COMPENSATION_WALLET_URL" src dev .vault --glob '!*.pyc'` -> `pass`
- `verify:` `uv run python -c "from dev.quality.unused_symbol_coverage import run_gate; ..."` -> `pass` (374 live symbols, 20 orphan tests, removed aliases absent)

## Notes

The broader affected application selection ran 86 tests: 85 passed and the live route-ownership gate named `donativo_donor`, `gasto193_contributor`, `refund_operation`, and `related_party_operation` as declared registry sources with no executable route. They remain red for their owning registry or resolver mechanisms; no deferred list or accepted-set alias was restored.
