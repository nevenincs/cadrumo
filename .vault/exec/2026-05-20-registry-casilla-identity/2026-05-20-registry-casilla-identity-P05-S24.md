---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S24'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P05.S24`

Extended the Modelo 200 registry test to assert the Liquidación
cuota-chain casillas resolve under their segment-scoped identity and that
the page-014 fichero-BOE export binding resolves casilla `00562` to the
Liquidación occurrence rather than the ECPN one.

- Modified: `src/aeat/domain/calculations/registry/test_modelo_200_registry.py`

## Description

Two tests were added to the Modelo 200 registry suite, both backed by a
real `build_snapshot` of the committed registry.

`test_modelo_200_liquidacion_cuota_chain_casillas_resolve_under_their_segmento`
resolves each of the six Liquidación cuota-chain casillas by its composed
`(segmento:number)` id on the built snapshot and asserts it carries the
expected `segmento` and bare `number`: `00552`, `00558`, `00562` under
the Liquidación III segment `DP200014`, and `00592`, `00599`, `00611`
under the Liquidación IV segment `DP200014B`. Each is additionally
asserted to carry non-empty `legal_refs` and `source_refs` — the
calculation-grounding contract.

`test_modelo_200_page_014_export_binding_resolves_00562_to_liquidacion`
resolves the Modelo 200 fichero-BOE export layout on the built snapshot
and asserts the `modelo-200-page-014-casilla-00562` export field binds
the Liquidación `DP200014:00562` casilla, not the ECPN occurrence of the
same five-digit number. It then resolves that bound casilla back on the
revision and confirms its `segmento` is `DP200014` and `number` is
`00562`. This proves the P04 export re-point landed: before the
segment-scoped identity model, number `00562` could resolve only to the
single declarable occurrence, which was the ECPN one.

The `resolve_export_layout` re-export was added to the module import
block.

## Tests

`pytest test_modelo_200_registry.py` — 5 tests pass, including the two
new segment-identity and export-binding assertions. `ruff check` on the
touched file is clean. No mocks or skips: both tests build a real
snapshot of the committed registry and query the resolved layout.
