---
tags:
  - '#plan'
  - '#assets-core'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-assets-core-amortization-method-set-adr]]'
  - '[[2026-09-21-assets-core-lifecycle-contract-adr]]'
  - '[[2026-09-21-assets-core-cost-basis-stages-adr]]'
  - '[[2026-09-23-assets-core-vehicle-affectation-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:66083aa9c456f46c6ec37df7c33570834c7305582a1d2ccb4e4aa4252931d6d5'
---

# `assets-core` plan

Complete the grounded 2025 IRPF activity amortization method set and prove one non-linear asset end to end through installed CLI and TUI.

## Description

Approved 2026-09-23. Basis: the operator-coordinated ASSETS-01 continuation brief relayed by CADRUMO-ADMIN on 2026-09-23, which assigns limits 1, 2, 3 and 5 as this session's bounded goal, together with the operator's standing instruction that pipeline phases proceed without approval stops.

Decision coverage: `2026-09-23-assets-core-amortization-method-set-adr` governs the election contract, method admission and method arithmetic (S01-S06). `2026-09-21-assets-core-lifecycle-contract-adr` and its cost-basis amendment `2026-09-21-assets-core-cost-basis-stages-adr` continue to govern identity, claims, projections and allocation. The legal evidence is `2026-09-23-assets-core-amortization-method-set-research`. Limits 1, 2 and 5 of the brief (namespace tripwire, private parity import, current-generation re-verification) were routine corrections completed before this plan in commits `faf9b18bc7` and `a2e62cdb55`.

S09-S12 were added on 2026-09-23 under the operator's instruction that every critical issue found is actioned, with the ordering and scope set by CADRUMO-ADMIN on the operator's behalf. `2026-09-23-assets-core-vehicle-affectation-adr` governs S09's vehicle work and the method-set amendment of 2026-09-23 governs its other admissions; S11 consumes the average-workforce field the taxpayer-profile schema version 7 adds.

## Steps

- [x] `S01` - Enrol the 2025 method-admission, class-admission, weighting, threshold and incentive authority with legal entries and manual citations; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`.
- [x] `S02` - Carry the amortization election and acquired condition on the immutable revision and implement every admitted method schedule; `src/cadrumo/domain/renta/actividad_asset/`.
- [x] `S03` - Resolve the revision election through registry authority and delete the per-call selector; `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`.
- [x] `S04` - Route forecasts through the revision election with claim-history summaries and method-continuity refusal; `src/cadrumo/application/actividad_asset/`.
- [x] `S05` - Project the election contract through the CLI and TUI adapters; `src/cadrumo/entrypoints/`.
- [x] `S06` - Prove each method with independent worked examples, boundaries and cited refusals; `src/cadrumo/domain/renta/actividad_asset/tests/`.
- [x] `S07` - Publish the authority once and prove a non-linear asset through installed CLI and TUI to M130, M100 and the 2025 XSD; `dev/acceptance/assets/`.
- [ ] `S08` - Run the owning quality gates and write the checkpoint and handoff; `.agents/session-briefs/handoffs/`.
- [x] `S09` - Admit the table-listed intangible methods, reduced-size acceleration of indefinite-life intangibles and goodwill, and vehicles on a typed affectation declaration with electric-vehicle free depreciation; `src/cadrumo/domain/renta/actividad_asset/vehicle_affectation.py`.
- [x] `S10` - Give the undeclared-vehicle refusal a typed recovery action to the CLI and TUI correction; `src/cadrumo/application/actividad_asset/`.
- [ ] `S11` - Consume the average-workforce profile fact for job-creating and renewable self-consumption free depreciation; `src/cadrumo/domain/renta/actividad_asset/workforce.py`.
- [ ] `S12` - Republish the authority once after the format cutover and prove the final tree through one installed run; `dev/acceptance/assets/`.
- [ ] `S13` - Give the average-workforce profile field a typed CLI and TUI write path against the committed schema version 7, ahead of the S11 resolver wiring; `src/cadrumo/entrypoints/cli/config/`.

## Parallelization

Sequential. S02-S05 change one contract across the domain, the resolver, the application layer and both frontends, and they land together. S07 depends on the single authority republish that follows S01.

## Verification

- Each method has an independent hand-calculated oracle at a normal case and at its boundaries: first and last partial year, maximum-coefficient cap, minimum-period bound, residual value, and change of method. Refusals are asserted by type and provision.
- The resolver is exercised against the compiled registry and the published authority generation, never against a mocked table.
- Installed CLI and TUI each create, forecast, claim and hand off one non-linear asset. M130 and M100 reflect the claim, and the M100 XML passes the pinned 2025 XSD. A sanitized receipt records the source commit, the wheel SHA-256, the authority generation and the installed package hash.
- Ruff, ruff format, ty, basedpyright strict and pyrefly pass on every changed file. The import gate shows no finding sourced from asset modules.
