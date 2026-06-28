---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S94'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---


# W11.P25.S94 live marker and access-gate inventory

Scope: Wave W11, Phase P25, Step S94.

## Description

- Inventory `AEAT_LIVE_TESTS_ENABLED` usages with `rg`.
- Inventory `live_read`, `live_write`, `unit`, pytest hooks, and marker taxonomy owners.
- Inventory `AeatAccessGate`, `require_live_read`, `require_live_write`, and live-read gate call sites.
- Route `vaultspec-rag` discovery through the running service after local-store lock failures.
- Validate the current gate split with focused access-gate, auth-gate, marker-integrity, and Ruff checks.
- Fix the incidental marker-order regression in `test_modelo_work_ux.py`.
- Fix the incidental unused-normalized-EUR regression in `test_ledger_corpus_fidelity.py`.

## Outcome

The inventory found that current code treats `AEAT_LIVE_TESTS_ENABLED` as a pytest opt-in rather than an operator CLI switch. Production live-read surfaces still call `require_live_read`, but current `AeatAccessGate` only refuses when `PYTEST_CURRENT_TEST` is present and the validated setting is not the exact string `1`. Live writes remain permanently forbidden by `require_live_write`, and the pytest marker hook still drops `live_write` items at collection.

Focused validation passed after the incidental regressions were fixed:

- `uv run pytest src/aeat/core/access_gate/test_override.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/tests/test_marker_integrity.py -q` passed with 2106 tests.
- `uv run ruff check src/aeat/core/access_gate src/aeat/tests src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/entrypoints/cli/test_modelo_work_ux.py` passed.

No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

`vaultspec-rag` is not healthy enough to rely on as the only discovery route in this worktree. Direct local-store search reported a locked Qdrant store, service-routed narrow searches returned empty results, and broader service-routed searches timed out until their stale search processes were terminated by exact command-line match. This degradation remains open under W10.P24.S98.

The first focused validation run failed for two unrelated local regressions: `test_modelo_work_ux.py` had `pytestmark` below a module assignment, and `test_ledger_corpus_fidelity.py` computed an EUR-normalized amount but passed the raw amount to the IVA base helper. Both were fixed before S94 was closed.
