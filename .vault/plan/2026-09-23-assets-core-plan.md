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
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:d719f95a0da5f22a0257af4eed1a7920483091239d6c697518f6815a67a0f5fe'
---

# `assets-core` plan

Complete the grounded 2025 IRPF activity amortization method set and prove one non-linear asset end to end through installed CLI and TUI.

## Description

Approved 2026-09-23. Basis: the operator-coordinated ASSETS-01 continuation brief relayed by CADRUMO-ADMIN on 2026-09-23, which assigns limits 1, 2, 3 and 5 as this session's bounded goal, together with the operator's standing instruction that pipeline phases proceed without approval stops.

Decision coverage: `2026-09-23-assets-core-amortization-method-set-adr` governs the election contract, method admission and method arithmetic (S01-S06). `2026-09-21-assets-core-lifecycle-contract-adr` and its cost-basis amendment `2026-09-21-assets-core-cost-basis-stages-adr` continue to govern identity, claims, projections and allocation. The legal evidence is `2026-09-23-assets-core-amortization-method-set-research`. Limits 1, 2 and 5 of the brief (namespace tripwire, private parity import, current-generation re-verification) were routine corrections completed before this plan in commits `faf9b18bc7` and `a2e62cdb55`.

## Steps

- [x] `S01` - Enrol the 2025 method-admission, class-admission, weighting, threshold and incentive authority with legal entries and manual citations; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0002-activity-asset-amortization.toml`.
- [x] `S02` - Carry the amortization election and acquired condition on the immutable revision and implement every admitted method schedule; `src/cadrumo/domain/renta/actividad_asset/`.
- [x] `S03` - Resolve the revision election through registry authority and delete the per-call selector; `src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`.
- [x] `S04` - Route forecasts through the revision election with claim-history summaries and method-continuity refusal; `src/cadrumo/application/actividad_asset/`.
- [x] `S05` - Project the election contract through the CLI and TUI adapters; `src/cadrumo/entrypoints/`.
- [x] `S06` - Prove each method with independent worked examples, boundaries and cited refusals; `src/cadrumo/domain/renta/actividad_asset/tests/`.
- [x] `S07` - Publish the authority once and prove a non-linear asset through installed CLI and TUI to M130, M100 and the 2025 XSD; `dev/acceptance/assets/`.
- [ ] `S08` - Run the owning quality gates and write the checkpoint and handoff; `.agents/session-briefs/handoffs/`.

## Parallelization

Sequential. S02-S05 change one contract across the domain, the resolver, the application layer and both frontends, and they land together. S07 depends on the single authority republish that follows S01.

## Verification

- Each method has an independent hand-calculated oracle at a normal case and at its boundaries: first and last partial year, maximum-coefficient cap, minimum-period bound, residual value, and change of method. Refusals are asserted by type and provision.
- The resolver is exercised against the compiled registry and the published authority generation, never against a mocked table.
- Installed CLI and TUI each create, forecast, claim and hand off one non-linear asset. M130 and M100 reflect the claim, and the M100 XML passes the pinned 2025 XSD. A sanitized receipt records the source commit, the wheel SHA-256, the authority generation and the installed package hash.
- Ruff, ruff format, ty, basedpyright strict and pyrefly pass on every changed file. The import gate shows no finding sourced from asset modules.
