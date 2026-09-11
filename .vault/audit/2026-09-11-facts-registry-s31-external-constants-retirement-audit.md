---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:59c02d4a3fccf72c15fcda47c20ec15bee3ef1682427222d5e32c57f0f38ac34'
related: []
---
# `facts-registry` audit: `s31 external constants retirement`

## Scope

Reviewed plan step `W04.P16.S31`, the external-constants retirement reference, the source deletion, retirement ledger, and focused gate. Verified the current repository has no production reference to a removed statutory declaration or statutory-constant adapter/fallback; the two remaining model sets are the documented aggregation-routing and calendar-coverage values. Exercised the focused retirement and authored-statutory-facts suites.

## Findings

### negative-census | medium | An unannotated statutory declaration can evade the retirement census

`_top_level_constants` reports only `ast.AnnAssign` nodes. A module-level plain assignment such as `NEW_TAX_THRESHOLD = Decimal("1")`, inserted before `RETENCIONES_MODELOS`, is absent from the observed constants list: the retired-symbol, technical-prefix, and two-symbol-tail assertions all still pass. The same gate also limits its import census to `src/cadrumo`, excluding the shipped `src/cadrumo_harness` package. The current source is clean, and the eight focused tests pass, but the negative gate does not prove that a future stray legal constant fails closed.

### negative-census | resolved | The census now covers every public module binding across shipped roots

Verified the correction: `_public_module_bindings` includes both annotated and plain module-level name bindings; the exact technical-prefix and routing-tail checks therefore reject a stray declaration. The focused defect proof confirms that an unannotated binding enters the census, and the direct-import scan now covers both `src/cadrumo` and `src/cadrumo_harness`. The five-test census suite and Ruff both pass.

## Recommendations

- For `negative-census`, enumerate all module-scope public bindings, including both `ast.AnnAssign` and `ast.Assign`, and assert an exact allowed symbol inventory: retained technical configuration plus `RETENCIONES_MODELOS` and `IVA_REGIME_MODELOS`. Extend the production scan to every shipped source root and add an isolated `Assign`-based statutory-constant defect proof that must fail the gate.

- Resolved: the preceding recommendation has been implemented and independently verified; no open S31 review recommendations remain.
