---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related: []
---



# `schema-hardening` audit: `m200-m202 pago-fraccionado relation drop`

## Scope

Cross-domain regression review of the modelo-200 (Impuesto sobre
Sociedades) Liquidación formula chain under the active schema-hardening
campaign. Triggered by a red cross-dependency test
(`test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados`)
during the codebase-health campaign's checkpoint sweep. The test
defends the M200 to M202 handoff: modelo 200's cuota del ejercicio a
ingresar must net out the modelo 202 pago-fraccionado instalments
already paid in-year.

## Findings

### Stale-test root cause — resolved diagnosis, MEDIUM

The original failure (`unknown registry input casilla ids: [00592]`)
is a stale test, not a registry defect. Commit `0364f576d`
re-numbered the M200 Liquidación casillas from bare ids to the
segment-qualified scheme: `00592` became `DP200014B:00592` (cuota
líquida) and `00599` became `DP200014B:00599` (cuota del ejercicio a
ingresar/devolver). The cross-dependency test was never updated and
still referenced the bare ids. A test edit modernising the ids to the
segment-qualified scheme is staged in the working tree against
`src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`;
it is correct against committed registry HEAD and is uncommitted
pending the formula adjudication below.

### M202 relation relocated, not dropped — RESOLVED, was HIGH

Initial review of the then-uncommitted `formulas.toml` WIP feared the
`DP200014B:00599` rewrite had dropped the modelo-202 pago-fraccionado
relation: the committed-HEAD form was
`subtract(DP200014B:00592, modelo-200-2024-rel-202-pagos-fraccionados)`
and the WIP form is a multi-term
`multiply(DP200026:00625 / 100, subtract-chain(...))` carrying no
reference to `modelo-200-2024-rel-202-pagos-fraccionados` on `00599`.

The WIP has since landed as commit `aae1bb60c` ("M200: correct
page-14 cuota chain against AEAT Manual de Sociedades 2024"). Review
of the committed registry confirms the M202 relation was NOT dropped
— it was relocated. `modelo-200-2024-rel-202-pagos-fraccionados` is
still defined in `relations.toml`, classified in
`dependency_classifications.toml`, and declared on a construct in
`constructs.part-002.toml`. The M200 to M202 netting required by
Ley 27/2014 art. 41 remains modelled; the schema-hardening campaign
grounded the restructure against the AEAT official manual. No
unlawful-settlement regression. The remaining work is purely to
re-point the cross-dependency test to the relation's new casilla and
formula location.

## Recommendations

The adjudication this finding originally called for is resolved by
commit `aae1bb60c`: the M202 relation moved rather than dropped, so
the only remaining action is test alignment.

1. Re-point the cross-dependency test
   (`test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados`)
   to assert the M200 to M202 pago-fraccionado netting at the
   relation's new casilla and formula location — segment-qualified
   ids, current formula `operand_refs`. Tracked as task #51.
2. The test must remain a graph-wiring / aggregation-linkage
   assertion. Do not close it as tautological or weaken it to a shape
   that no longer defends the netting — the M200 to M202 linkage is a
   Ley 27/2014 art. 41 legal requirement, not an arbitrary numeric
   expectation.
3. No further registry-data action is required; the schema-hardening
   restructure is grounded against the AEAT Manual de Sociedades 2024
   and the registry is internally coherent.
