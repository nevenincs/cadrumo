---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:06501f1aa890be18e75bc77307b1aad6d43dfb8c248e3fd343b34166d0f91a84'
related:
  - '[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]'
  - '[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]'
  - '[[2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit]]'
  - '[[2026-08-05-modelo-parity-rollup-plan]]'
---
The question is whether Modelo 100 revision 2025 casillas 0150, 0613, and 1481 can be promoted to automatic producers now. The grounded evidence does not yet support production promotion: each row has a distinct missing contract. The evidence-supported interim shape is a focused addendum per row with independent runtime oracles and reverse wiring; the existing manual declarations plus bounded negative guards remain honest until SOL adjudicates the addenda.

## Findings

### S16 / 0150: rental calculation capability exists, but no enrolled calculation source exists

The 2025 0150 schema has the rental-reduction semantic role and official 2025 sources but no producer declaration. The 2024 analogue is a formula target whose formula consumes a rental-tier operator binding. Source: src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0101-c0150.toml:1-8; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0149-c0150.toml:1-9; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0183-renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2.toml:1-25.

The rental register is year-aware: compute_finca_aggregates returns a rounded reduccion_arrendamiento_vivienda total and per-contract tier attribution, while resolve_reduccion reads revision-scoped 2025 parameters. Sources: src/cadrumo/domain/fincas/_aggregates.py:85-113; src/cadrumo/domain/fincas/_aggregates.py:219-238; src/cadrumo/domain/fincas/_tier_resolver.py:168-244; src/cadrumo/domain/fincas/_tier_resolver.py:406-475. That is calculation capability, not application wiring. fincas_source_readiness() explicitly returns ready=False because rendimento and amortization state do not cross the canonical secure-storage revision boundary. Source: src/cadrumo/domain/fincas/_source_readiness.py:34-52. Exact-symbol confirmation finds the aggregate only in the domain and domain tests; no application source resolver enrolls it.

The candidate 0150 contract needs: canonical persisted source state; an application resolver owned by a declared source kind; a registry binding/selector targeting exactly 0150; explicit one/multiple-contract, active-period, zero/non-qualifying, expense/amortization attribution, and rounding semantics; 2025 legal/source citations and an independent worked example; typed provenance from finca, contract, income, expense, and amortization observations; reverse wiring proving the 0150 producer, binding, and formula/aggregate ID agree; and a real secure-storage/operator-calculate proof. Cloning the 2024 tier-input formula is cheaper, but it preserves an operator-only producer and does not close the source contract.

### S17 / 0613: the derived family path is year-dynamic, but the statutory cap fact is 2024-only

The 2025 0613 casilla is manual and cites Article 81 plus the 2025 form; 2024 has a formula target with three inputs. Sources: src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0595-c0613.toml:1-9; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0181-renta-2024-incremento-guarderia-0613.toml:1-21.

The canonical profile injector derives guardería population and actual spend for whatever filing year declares those selectors. Sources: src/cadrumo/application/modelo/_profile_binding.py:235-286; src/cadrumo/domain/contribuyente/family.py:1291-1316. The third term is not equivalent: RentaFamilyProfile exposes cotizaciones_ss_madre_2024 and documents it as the Article 81.2 cap, and the profile schema exposes only that 2024 operator fact. Sources: src/cadrumo/domain/contribuyente/family.py:1178-1184; src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:19-21; src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1651-1657.

The candidate 0613 contract needs: a versioned 2025 cap fact with profile schema/model serialization and provenance; 2025 bindings for spend, population, and cap; a 2025 formula with exact minimum and rounding semantics; Article 81/2025 source citations on casilla, formula, bindings, and observations; reverse target parity proving 0613 is computed by that formula and the formula consumes the same binding IDs; and real profile-to-calculate tests with independent oracles for spend-limited, child-count-limited, cap-limited, zero, and turning-three monthly-detail cases. Adding only 2025 registry rows is insufficient because it leaves the cap unresolved or silently reuses a 2024 fact. Extending the versioned fact and formula together is viable only through a focused addendum and SOL approval.

### S18 / 1481: 2024 handoff is complete, while 2025 lacks the relation and target binding

The 2024 schema declares 1481 as a bound casilla with renta-2024-modelo-131-rendimiento-neto-modulos; the relation and binding both select M131 casilla 01, sum four quarters, and target that binding. Sources: src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/1424-c1481.toml:1-9; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/relations/0008-renta-2024-rel-131-rendimiento-neto-modulos.toml:1-16; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0012-renta-2024-modelo-131-rendimiento-neto-modulos.toml:1-14. The live test proves four distinct quarterly values aggregate to 5400 and reach 1481/1482/1484. Source: src/cadrumo/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py:222-249.

The 2025 1481 schema is manual, and the only 2025 M131 relation is the payments handoff from casilla 15. Sources: src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/1479-c1481.toml:1-8; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/relations/0006-renta-2025-rel-131-pagos-fraccionados.toml:1-16; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0040-renta-2025-modelo-131-pagos-fraccionados.toml:1-14. M131 2025 casilla 01 is itself a manual module-result input, so a relation would transport an operator-grounded observation; it would not make the M131 coefficient engine computed. Source: .vault/adr/2026-07-01-modelo-131-eo-modulos-engine-adr.md.

The candidate 1481 contract needs: official 2025 evidence that annual M100 1481 consumes quarterly M131 01; a 2025 relation selecting source model 131/casilla 01 with four-quarter-to-annual alignment and sum aggregation; a matching relation-prefill binding and 1481 reverse wiring; activity/regime identity and clean-state semantics, including explicit zero for direct estimation and multiple-activity behavior; quarterly provenance; and a real four-quarter 2025 runtime oracle with distinct inputs and an independently expected total. Treating 2024 continuity as proof for 2025 is inference, not evidence.

### Comparative closure matrix

| Row | Current producer | Minimum promotion contract | Independent runtime oracle |
| --- | --- | --- | --- |
| 0150 | 2025 manual | fincas source enrollment, aggregate/rounding semantics, 2025 legal evidence, provenance, reverse wiring | real register with qualifying/non-qualifying and multi-contract cases |
| 0613 | 2025 manual | 2025 cap fact, profile schema/binding, formula, provenance, reverse wiring | real profile with spend/count/cap/turning-three cases |
| 1481 | 2025 manual | official 2025 M131-01 relation, target binding, activity identity, provenance, reverse wiring | four distinct 2025 quarters plus direct-estimation zero |

The available alternatives are (a) clone prior-year declarations, (b) promote from semantic-role continuity alone, or (c) keep the manual surface with a structural guard while preparing a focused addendum. The first two omit producer, legal, provenance, or runtime gates. Option (c) is the only currently evidence-supported interim shape; it is not final standardization.

## Sources

- .vault/research/2026-08-05-modelo-parity-rollup-s16-s18-evidence-research.md
- .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md
- .vault/audit/2026-08-05-modelo-parity-rollup-semantic-decision-boundary-audit.md
- src/cadrumo/domain/fincas/_source_readiness.py:34-52
- src/cadrumo/domain/fincas/_aggregates.py:85-113
- src/cadrumo/domain/fincas/_aggregates.py:219-238
- src/cadrumo/domain/fincas/_tier_resolver.py:168-244
- src/cadrumo/application/modelo/_profile_binding.py:235-286
- src/cadrumo/domain/contribuyente/family.py:1178-1184
- src/cadrumo/domain/contribuyente/family.py:1291-1316
- src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:19-21
- src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1651-1657
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0101-c0150.toml:1-8
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/1479-c1481.toml:1-8
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0149-c0150.toml:1-9
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0595-c0613.toml:1-9
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/1424-c1481.toml:1-9
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0183-renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2.toml:1-25
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0181-renta-2024-incremento-guarderia-0613.toml:1-21
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/relations/0008-renta-2024-rel-131-rendimiento-neto-modulos.toml:1-16
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0012-renta-2024-modelo-131-rendimiento-neto-modulos.toml:1-14
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/relations/0006-renta-2025-rel-131-pagos-fraccionados.toml:1-16
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0040-renta-2025-modelo-131-pagos-fraccionados.toml:1-14
- src/cadrumo/application/modelo/tests/test_modelo_100_m131_modulos_fold_in_live.py:222-249
- .vault/adr/2026-07-01-modelo-131-eo-modulos-engine-adr.md
- .vault/research/2026-05-20-calculation-source-connectivity-research.md
