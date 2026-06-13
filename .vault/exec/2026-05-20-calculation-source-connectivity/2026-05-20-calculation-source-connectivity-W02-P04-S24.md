---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S24'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P04.S24`

Added source-resolution fingerprint coverage for profile and live IVA wallet sources.

- Modified: `src/aeat/application/aggregation/_source_profile.py`
- Modified: `src/aeat/application/aggregation/test_source_mesh_profile_live.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/application/modelo/_borrador_binding.py`
- Modified: `src/aeat/application/modelo/_profile_binding.py`
- Modified: `src/aeat/application/modelo/__init__.py`
- Modified: `.vault/plan/2026-05-20-calculation-source-connectivity-plan.md`

## Description

The profile resolver now attaches a stable SHA-256 fingerprint for sourced profile facts, and the live IVA wallet path is exercised through the `IvaWalletDecisionSourceResolver` so decision provenance carries the resolver fingerprint into source resolution. Borrador provenance also includes a stable snapshot-derived fingerprint for sourced Modelo 100 values.

The Modelo 303 IVA compensation application path now consumes the wallet resolver output instead of writing the selected binding directly, preserving the explicit source-mesh contract for that live source family.

## Tests

Ran `uv run pytest src/aeat/application/aggregation/test_source_mesh_profile_live.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py`: 44 passed.
