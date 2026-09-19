---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:ccadefa100404ea3d59a6a28556a30e08ac7b7615dfe2aeab55efe521c42ba99'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
---

# `registry-temporal-coverage` audit: `S46 Modelo 188 design-era review`

## Scope

Independent review of `bb0b9b2201`, its reconstructed S46 execution record, the temporal-coverage plan and M188 design-era evidence, the M188 revision, legal and source catalogues, official corpus, and focused registry tests.

## Findings

### s46-source-era | low | the 2023 source is the sole legitimate design authority

The bundled AEAT PDF hash and 106,418-byte length match `aeat-dr-188-2023`, whose applicability begins on 2023-01-01 without an end date. The renamed revision selects only from that year, retains applicability grade, and rejects each 2019--2022 annual coordinate. The 2023 source is therefore not backdated.

### s46-stale-consumers | low | the revision rename initially left three consumer surfaces stale

The renamed source tree was internally consistent, but the summary-parity test still selected `2019-y-siguientes`, the four M188 locale schema files retained that revision key, and the continuity explanation still claimed a 2019 validity start. The test would dereference a missing revision; the locale and provenance records would state an obsolete identity. All were retargeted to `2023-y-siguientes` or 2023-01-01 in this review.

### s46-capability-boundary | low | the constraint does not create filing capability

The revision has the five existing manual summary casillas and no formulas. It has no export-layout or M188 producer namespace, so the exact 2023 source does not become a filing, rendering, or value-owner claim. The reference's historical-design and complete output-chain prerequisites remain unsatisfied.

## Recommendations

Retain the 2023-only applicability boundary and the explicit historic-year refusal. Any earlier-year selection requires separately hash-pinned exact historic authority; any output capability also requires the complete provenance, semantic-map, generated-fragment, and emitted-byte chain.
