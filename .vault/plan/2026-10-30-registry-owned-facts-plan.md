---
tags:
  - '#plan'
  - '#registry-owned-facts'
date: '2026-10-30'
tier: L1
modified: '2026-10-31'
body_schema: body-v2
body_hash: 'sha256:e40343a46a2619c2fef7fd233a403a3b4fd36f58a120693e533a7a6116c31de0'
---

# `registry-owned-facts` plan

## Description

Approved 2026-10-30. Basis: the operator's instruction of 2026-10-30 that no number, limit or threshold is kept in the codebase and that the facts schema is the authority.

Move every remaining tax number, limit, period rule and form code from production code to the registry, and publish the authority. Coverage: no new costly decision; this applies settled registry ownership in the accepted registry decisions and the rule above. Calendar facts, pure arithmetic, technical limits and registry ids stay in code. Evidence is the sweep recorded in `2026-09-21-assets-core-audit`. Only one writer edits the registry and publishes at a time, because a publish refuses while its sources move. Each move preserves behaviour per revision and reports any revision where the code and the registry disagree.

## Steps

- [x] `S01` - Replace code copies of values the registry already holds: the DT12 threshold, Modelo 190 and 280 offsets, Modelo 720 subclaves; `src/cadrumo/application/modelo/dt12_advisory.py, src/cadrumo/application/filing/, src/cadrumo/domain/foreign_assets/register.py`.
- [x] `S02` - Derive box lists from registry declarations per revision; `src/cadrumo/application/modelo/projection.py, src/cadrumo/application/calculations/, src/cadrumo/domain/calculations/registry/`.
- [x] `S03` - Move form claves and code tables into registry vocabularies; `src/cadrumo/application/filing/, src/cadrumo/domain/contribuyente/renta_codes.py, src/cadrumo/application/wizard/, src/cadrumo/domain/calculations/registry/withholding_bindings.py`.
- [ ] `S04` - Move modelo routing rules and sets into registry declarations; `src/cadrumo/application/aggregation/, src/cadrumo/domain/calculations/registry/applicability.py, src/cadrumo/domain/deadlines/`.
- [ ] `S05` - Move period rules with legal force into the registry; `src/cadrumo/domain/period.py, src/cadrumo/domain/renta/maritime_exemption.py`.
- [ ] `S06` - Extend the literal gate across domain and application, covering field bounds, box ids and letter claves, and republish the authority; `dev/quality/tests/`.
- [ ] `S07` - Bind the Modelo 100 elemento patrimonial rows as repeated rows per sale; `src/cadrumo/domain/calculations/registry/actividad_asset_disposal_bindings.py, src/cadrumo/_data/registry/aeat/modelos/100/`.

## Parallelization

## Verification
