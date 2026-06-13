---
tags: ["#exec", "#live-iva-compensation-wallet"]
date: "2026-05-21"
modified: '2026-05-21'
step_id: "S01"
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

# `live-iva-compensation-wallet` `W03.P01.S01`

Verified and hardened the IVA ledger aggregation input boundary for ordinary IVA, recargo de equivalencia, exenciones, intra-community reverse charge, OSS/IOSS separation, and signed adjustments.

- Modified: `src/aeat/application/aggregation/_iva_ledger.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/aggregation/test_iva_ledger.py`
- Modified: `.vault/audit/2026-05-20-live-iva-compensation-wallet-review.md`

## Description

The existing transaction-backed projector remains limited to ordinary domestic IVA that can be inferred from ledger direction plus a canonical Spanish IVA rate. That path is intentionally not expanded to guess non-domestic operation categories from bank rows.

Added a separate pre-classified IVA candidate boundary for facts whose IVA category, rate kind, and flow direction must come from upstream invoice or operation evidence. The new candidate path accepts signed base and IVA amounts so adjustment rows can be represented without forcing them through non-negative domestic transaction projection. It blocks non-declarable sentinel categories before registry binding resolution.

The generic IVA candidate path now feeds the registry's existing `ledger_iva_aggregation` resolver. OSS/IOSS stays on the existing Modelo 369-specific candidate and validation path.

The rolling audit now records `WALLET-036` as the W03.P01.S01 calculation coverage gap and its mitigation.

The vaultspec CLI can query the L3 plan, but exact step closure remains unsafe for duplicate leaf ids: `vault plan step check` accepts only `S##`, not `W03.P01.S01`. The exact W03 row was closed by direct checkbox edit to avoid mutating a different duplicate `S01` row.

## Tests

- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py -q` completed with 23 passed.
- `uv run pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/test_oss_ioss.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q` completed with 58 passed.
- `uv run ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py` passed.
- `git diff --check -- src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py` passed.
