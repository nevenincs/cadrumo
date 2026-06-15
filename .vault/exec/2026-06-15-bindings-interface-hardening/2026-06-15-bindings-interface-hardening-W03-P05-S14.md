---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S14'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace bindings-interface-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-06-15-bindings-interface-hardening-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The generalise the IVA unsupported-observation screen into a per-family unrouted-observation screen that flags an unrouted declarable observation for every aggregation family and ## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/application/aggregation/_source_mesh.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# generalise the IVA unsupported-observation screen into a per-family unrouted-observation screen that flags an unrouted declarable observation for every aggregation family

## Scope

- `src/aeat/domain/calculations/registry/_ledger_bindings.py`
- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Study the IVA screen `unsupported_ledger_iva_observations`: it inspects each declarable observation against every `ledger_iva_aggregation` binding selector (category, rate_kind, flow_direction), returns the tuple of observations no binding selects, and excludes the by-law cuota-less categories as the false-fire guard.
- Generalise that shape into three sibling registry-layer screens, one per live aggregation family: `unsupported_ledger_renta_expense_observations` (match modelo/period/target_casilla), `unsupported_ledger_renta_income_observations` (match target_casilla), and `unsupported_ledger_oss_observations` (match regime/destination/rate/direction/transaction_kind).
- Carry the family-appropriate false-fire guard: an observation whose declarable magnitude is zero (zero deductible amount; zero gross-and-base income; zero base and zero IVA on OSS) contributes nothing whether routed or not and is excluded, mirroring the cuota-less precedent.
- Add a `unrouted_observation` member to the `CalculationSourceDiagnosticReason` closed Literal so each screen surfaces a typed advisory rather than a silent zero.
- Re-export the three new functions through the registry facade and package `__all__`.

## Outcome

Each live aggregation resolver family now has a fail-closed screen with the same shape as the IVA precedent, returning the unrouted declarable observations and respecting a legitimately-zero false-fire guard. The wiring onto the live calculate path is S15; the tests are S16.

## Notes

The screens are scoped to the families that run live in the mesh tuple (IVA, renta expense, renta income, OSS); the resolver-less deferred source kinds remain advisory through the existing unhandled-source net and are not in scope. The mesh enrollment, owned-vs-deferred ownership, and novel-source gate were not touched.
