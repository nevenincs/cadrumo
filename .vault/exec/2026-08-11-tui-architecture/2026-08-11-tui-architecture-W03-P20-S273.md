---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:437aade8cde0ed24037ba336b336459dc283b6322ecd56e442e9b56e589eaad7'
step_id: 'S273'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retire the 9 withholding_bindings re-export(s) from the registry bindings dispatch module by direct-importing WithholdingClaveBreakdown, WithholdingObservation, WithholdingObservationRequirement, WithholdingTotalsParity, aggregate_withholding_by_clave, compute_withholding_totals_parity and others from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols.

## Scope

- `src/cadrumo/domain/calculations/registry/withholding_bindings.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `verify:` `grep -rn "from ...bindings import" across every tracked src/, dev/ and docs/ .py file, matched against every retired symbol name` -> `pass` (zero external reach beyond the two commits' surviving `__all__` names)

## Notes

No code changes in this Step: the export retirement (dropping these symbols from
`bindings.py`'s `__all__` and import block) had already landed in `6d47c1a9c5`
("export only locally defined symbols from four facades"), a peer commit that
independently found four of five affected rows already marked complete with
their export half never done. This Step's own remaining proof obligation --
zero remaining reach through the dispatch module -- was verified directly
rather than accepted on the peer commit's message: grepped every
`from [module ending in bindings] import (...)` block across all tracked
`.py` files under `src/`, `dev/` and `docs/` for WithholdingClaveBreakdown, WithholdingObservation, WithholdingObservationRequirement, WithholdingTotalsParity, aggregate_withholding_by_clave, compute_withholding_totals_parity, and the remaining withholding_bindings re-exports, confirmed no
consumer imports any of them from `bindings.py` (only from their real
defining module, `withholding_bindings.py`), and confirmed `bindings.py` itself no
longer imports or references them. Both halves of the Step's proof
obligation are true on evidence, so no further change was required.
