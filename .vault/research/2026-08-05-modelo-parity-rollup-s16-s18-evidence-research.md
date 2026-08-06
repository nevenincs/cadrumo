---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:7815f0f38c22a0dc5689ddf33ab95617600c9762a406240bfe4af73a59d867ff'
related:
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
  - "[[2026-08-04-modelo-100-casilla-implementation-audit]]"
---
# modelo-parity-rollup research: M100 2025 semantic evidence tranche

The evidence question is whether Modelo 100 revision 2025 casillas 0150, 0613, and 1481 can be promoted from manual surfaces to computed or relation-backed producers. The current evidence picture supports preserving the three manual classifications until three different contracts are grounded: per-contract rental eligibility for 0150, year-2025 monthly guarderia facts for 0613, and an independently proven annual M131-to-M100 mapping for 1481. Prior-year declarations are not sufficient authority for any of the three.

## Findings

### 2025 casilla 0150 has official legal and form evidence but lacks a complete producer input contract

The 2025 schema declares 0150 with its rental-reduction semantic role and 2025 dictionary/manual sources, but no input_kind or formula target (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0101-c0150.toml:1-8). The 2024 surface is explicitly computed by renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2 (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0149-c0150.toml:1-10; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0183-renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2.toml:1-27).

The bundled 2025 Manual explains the Article 23.2 contract-date split and the 50, 60, 70, and 90 percent rates (src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf, pages 283-285). The 2025 form surface contains a contract date and reduction flag (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0247-c0093.toml:1-9; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0252-c0100.toml:1-9), but the current tree does not expose every fact needed to distinguish the increased-rate conditions, multiple contracts, or the required aggregation semantics as a grounded profile/operator contract.

Options are:

- Copy the 2024 formula: rejected because it treats a prior-year producer as annual-law evidence.
- Keep 0150 manual: evidence-safe until the missing typed facts and independent worked-example mapping exist.
- Author a 2025 producer addendum: viable only with contract identity, dates, eligibility flags, rate selection, multi-contract aggregation, provenance, reverse wiring, and an independent 2025 numeric example.

### 2025 casilla 0613 has a documented calculation rule but no 2025 profile fact surface

The 2025 schema declares 0613 as a manual semantic surface with Article 81 and 2025 form/manual sources (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8). The 2024 declaration and formula are explicitly computed and use three 2024 bindings (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0595-c0613.toml:1-10; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0181-renta-2024-incremento-guarderia-0613.toml:1-20).

The 2025 Manual establishes qualifying complete months, the annual 1,000-euro limit, effective non-subsidized expenses, age-transition months, employer payments, and declaration destination 0613 (src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf, pages 1387-1391). The current 2025 registry has no guarderia, monthly custody, or 2025 cotizaciones profile binding; the existing implementation and profile method are 2024-scoped (.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:190-206).

Options are:

- Extend the 2024 minimum formula unchanged: rejected because the 2025 Manual monthly and subsidy rules are not represented by current annual bindings.
- Keep 0613 manual: evidence-safe while the fact contract is missing.
- Add a 2025 profile/runtime contract: viable only after defining per-child monthly eligibility, complete-month expense, subsidies/employer payments, age transitions, caps, provenance, and independent real-runtime examples.

### 2025 casilla 1481 has a plausible upstream candidate but no proven annual mapping

The 2025 schema declares 1481 as a manual EO reduced-income surface with 2025 form, dictionary, manual, procedure, and Renta WEB sources (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/1479-c1481.toml:1-9). The 2024 declaration is relation-bound to renta-2024-modelo-131-rendimiento-neto-modulos (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/1424-c1481.toml:1-10; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0012-renta-2024-modelo-131-rendimiento-neto-modulos.toml:1-14).

The candidate source is not a computed M131 result: M131 2025 casilla 01 is itself a manual filed observation (src/cadrumo/_data/registry/aeat/modelos/131/revisions/2025/casillas/0001-c01__c15.toml:1-11). The 2025 M131 internal modules engine is a separate internal calculation surface, and the 2025 M100 dependency currently declares only the M131 payments relation (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/dependency_classifications/0005-renta-2025-dep-131.toml:1-8; src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/bindings/0040-renta-2025-modelo-131-pagos-fraccionados.toml:1-7). No 2025 relation or binding maps quarterly M131 01 to annual M100 1481.

Options are:

- Copy the 2024 relation: rejected until activity identity, annual adjustment semantics, and evidence prove that a quarterly sum is the correct 2025 annual source.
- Keep 1481 manual: evidence-safe under the current dependency graph.
- Author a 2025 cross-model addendum: it must settle the exact mapping M131/2025/01/1T..4T to M100/2025/0A/1481, relation kind, activity identity, aggregation, provenance, clean-state behavior, multi-activity handling, and an independent numeric oracle.

### The authorizing contract makes the missing evidence an implementation gate

The parity ADR says revision evidence is only a floor, numeric correctness needs independent evidence, bulk cloning and these three production changes are deferred, and any new producer/relation/profile contract must return to SOL ( .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md:52-58; :103). The prior M100 audit records the three rows as different semantic divergences and names the required follow-up work (.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:190-212; :241-247).

The evidence-favoring next tranche is to author the three candidate contracts and their independent-oracle acceptance matrices, then return those addenda to SOL. A structural test that merely asserts the current manual classification would protect the boundary but would not close the parity step. No production formula, binding, selector, profile, relation, or aggregation change is justified by this research alone.

## Sources

- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0101-c0150.toml:1-8
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/1479-c1481.toml:1-9
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0149-c0150.toml:1-10
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/0595-c0613.toml:1-10
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/casillas/1424-c1481.toml:1-10
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0181-renta-2024-incremento-guarderia-0613.toml:1-20
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0183-renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2.toml:1-27
- src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/bindings/0012-renta-2024-modelo-131-rendimiento-neto-modulos.toml:1-14
- src/cadrumo/_data/registry/aeat/modelos/131/revisions/2025/casillas/0001-c01__c15.toml:1-11
- src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf pages 283-285
- src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf pages 1387-1391
- .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md:52-58
- .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md:103
- .vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:190-212
- .vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:241-247
