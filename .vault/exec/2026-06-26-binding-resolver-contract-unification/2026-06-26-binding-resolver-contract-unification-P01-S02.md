---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S02'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Migrate the M349-only PerModeloRegistryBindingResolution consumer onto CalculationSourceResolution, then delete the PerModeloRegistryBindingResolution model and resolve_per_modelo_registry_binding_values in the same atomic relocation commit

## Scope

- `src/aeat/application/aggregation/_registry_provider.py`

## Description


Commit `52edec4b1` (covers S02 + S04). Deleted the vestigial M349-only
`_registry_provider` module (`PerModeloRegistryBindingResolution` +
`resolve_per_modelo_registry_binding_values` + its test) after confirming ZERO
production callers at HEAD. Dropped the two re-exports from the aggregation package
`__all__` / import surface (S04). Removed the dead `_COUNTERPART_BINDING_SOURCE_KINDS`
guard in `test_service.py`. Regenerated API doc stubs (orphan `_registry_provider.rst`
+ toctree line) in the same commit.

## Outcome

P01.S02 + S04 complete. The M349 counterpart binding resolution the deleted function
duplicated is reached in production through the live registry-binding mesh path
(the 349 collectible/payable invoice bindings, covered by
`test_modelo_349_intracomunitario_fidelity`, `test_counterpart_bindings`,
`test_modelo_349_registry`). No production path changed; no casilla value shifts.

## Notes


The `apidocs scaffold` run pulled in ~22 peer-module stub deltas (withholding,
invoices, casilla-id, refund modules from concurrent campaigns). Surgically reverted
all peer-drift stubs and kept ONLY my `_registry_provider.rst` deletion + its single
aggregation-toctree line, so the commit carries only my stub change.
