---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:6298d4b554398ded28ffa34bc39edf9adbe0a88f407dcdd4ba0a5a89598f309d'
related:
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
  - "[[2026-08-04-modelo-100-casilla-implementation-audit]]"
---
# modelo-parity-rollup research: M100 2025 semantic evidence tranche

The evidence question is whether Modelo 100 revision 2025 casillas 0150, 0613, and 1481 can be promoted from manual surfaces to computed or relation-backed producers. The current evidence picture supports preserving the three manual classifications until three different contracts are grounded: per-contract rental eligibility for 0150, year-2025 monthly guarderia facts for 0613, and an independently proven annual M131-to-M100 mapping for 1481. Prior-year declarations are not sufficient authority for any of the three.

## Findings

### 2025 casilla 0150 has official legal and form evidence but lacks a complete producer input contract

The 2025 schema declares 0150 with its rental-reduction semantic role and 2025 dictionary/manual sources, but no input_kind or formula target . The 2024 surface is explicitly computed by renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2 (the former source file; the former source file).

The bundled 2025 Manual explains the Article 23.2 contract-date split and the 50, 60, 70, and 90 percent rates (src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf, pages 283-285). The 2025 form surface contains a contract date and reduction flag (the former source file; the former source file), but the current tree does not expose every fact needed to distinguish the increased-rate conditions, multiple contracts, or the required aggregation semantics as a grounded profile/operator contract.

Options are:

- Copy the 2024 formula: rejected because it treats a prior-year producer as annual-law evidence.
- Keep 0150 manual: evidence-safe until the missing typed facts and independent worked-example mapping exist.
- Author a 2025 producer addendum: viable only with contract identity, dates, eligibility flags, rate selection, multi-contract aggregation, provenance, reverse wiring, and an independent 2025 numeric example.

### 2025 casilla 0613 has a documented calculation rule but no 2025 profile fact surface

The 2025 schema declares 0613 as a manual semantic surface with Article 81 and 2025 form/manual sources . The 2024 declaration and formula are explicitly computed and use three 2024 bindings (the former source file; the former source file).

The 2025 Manual establishes qualifying complete months, the annual 1,000-euro limit, effective non-subsidized expenses, age-transition months, employer payments, and declaration destination 0613 (src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf, pages 1387-1391). The current 2025 registry has no guarderia, monthly custody, or 2025 cotizaciones profile binding; the existing implementation and profile method are 2024-scoped (.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:190-206).

Options are:

- Extend the 2024 minimum formula unchanged: rejected because the 2025 Manual monthly and subsidy rules are not represented by current annual bindings.
- Keep 0613 manual: evidence-safe while the fact contract is missing.
- Add a 2025 profile/runtime contract: viable only after defining per-child monthly eligibility, complete-month expense, subsidies/employer payments, age transitions, caps, provenance, and independent real-runtime examples.

### 2025 casilla 1481 has a plausible upstream candidate but no proven annual mapping

The 2025 schema declares 1481 as a manual EO reduced-income surface with 2025 form, dictionary, manual, procedure, and Renta WEB sources . The 2024 declaration is relation-bound to renta-2024-modelo-131-rendimiento-neto-modulos (the former source file; the former source file).

The candidate source is not a computed M131 result: M131 2025 casilla 01 is itself a manual filed observation . The 2025 M131 internal modules engine is a separate internal calculation surface, and the 2025 M100 dependency currently declares only the M131 payments relation (the former source file; the former source file). No 2025 relation or binding maps quarterly M131 01 to annual M100 1481.

Options are:

- Copy the 2024 relation: rejected until activity identity, annual adjustment semantics, and evidence prove that a quarterly sum is the correct 2025 annual source.
- Keep 1481 manual: evidence-safe under the current dependency graph.
- Author a 2025 cross-model addendum: it must settle the exact mapping M131/2025/01/1T..4T to M100/2025/0A/1481, relation kind, activity identity, aggregation, provenance, clean-state behavior, multi-activity handling, and an independent numeric oracle.

### The authorizing contract makes the missing evidence an implementation gate

The parity ADR says revision evidence is only a floor, numeric correctness needs independent evidence, bulk cloning and these three production changes are deferred, and any new producer/relation/profile contract must return to SOL ( .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md:52-58; :103). The prior M100 audit records the three rows as different semantic divergences and names the required follow-up work (.vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:190-212; :241-247).

The evidence-favoring next tranche is to author the three candidate contracts and their independent-oracle acceptance matrices, then return those addenda to SOL. A structural test that merely asserts the current manual classification would protect the boundary but would not close the parity step. No production formula, binding, selector, profile, relation, or aggregation change is justified by this research alone.

## Sources

- src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf pages 283-285
- src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf pages 1387-1391
- .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md:52-58
- .vault/adr/2026-08-05-modelo-parity-rollup-five-domain-contract-adr.md:103
- .vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:190-212
- .vault/audit/2026-08-04-modelo-100-casilla-implementation-audit.md:241-247
