---
tags:
  - '#plan'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
tier: L1
related:
  - '[[2026-07-26-declaracion-real-render-verification-adr]]'
  - '[[2026-08-03-declaracion-real-render-verification-specimen-corpus-distribution-research]]'
modified: '2026-08-23'
body_schema: body-v1
body_hash: 'sha256:2ce0a36e6c19e10612f299755bb7f0f6c3e9f2455d14fe05efa1976f12725ab8'
---

# `issue-620-external-pdf-signal` plan

Turn externally sourced tax-form PDFs into honest, reproducible parser evidence without promoting third-party hosting or mutable metadata into AEAT authority.

## Description

The accepted real-render verification decision requires render-dependent claims to be measured against external document bytes and requires unproved claims to remain visible evidence gaps. This plan applies that rule to the PDFs discovered through third-party sites: inventory the bytes without assuming provenance, validate their physical properties, use blank layouts as adversarial parser inputs, and retain the explicit limitation that no externally grounded populated M130 value placement is available. The specimen-corpus distribution research governs checkout-only placement and prevents these authoring fixtures from becoming runtime dependencies.

## Steps

- [ ] `S01` - Inventory and fingerprint the externally sourced Modelo 130 plain and fillable PDFs; `src/cadrumo/tests/fixtures/external_layout_candidates/130/`.
- [ ] `S02` - Inventory and fingerprint the externally sourced Modelo 131 plain and fillable PDFs; `src/cadrumo/tests/fixtures/external_layout_candidates/131/`.
- [ ] `S03` - Inventory and fingerprint the externally sourced Modelo 303 plain and fillable PDFs; `src/cadrumo/tests/fixtures/external_layout_candidates/303/`.
- [ ] `S04` - Inventory and fingerprint the externally sourced Modelo 036 plain and fillable PDFs; `src/cadrumo/tests/fixtures/external_layout_candidates/036/`.
- [ ] `S05` - Inventory and fingerprint the externally sourced Modelo 349 plain and fillable PDFs; `src/cadrumo/tests/fixtures/external_layout_candidates/349/`.
- [ ] `S06` - Implement typed source classification and physical-byte validation for external layout candidates; `src/cadrumo/tests/fixtures/external_layout_candidates/`.
- [ ] `S07` - Add Modelo 130 production-parser regressions for printed-box discovery and zero fabricated blank values; `src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m130_external_layout.py`.
- [ ] `S08` - Add the cross-model external-layout outcome matrix with explicit unsupported and unavailable results; `src/cadrumo/adapters/inbound/declaracion/tests/test_external_layout_candidate_matrix.py`.
- [ ] `S09` - Correct Modelo 130 extraction-profile evidence claims and lock the operator advisory; `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/extraction_profiles/`.

## Parallelization

Steps S01 through S05 are independent acquisition and inventory actions. Step S06 consumes their metadata contract. Steps S07 and S08 depend on S06 and the available inventory rows. Step S09 follows the measured M130 result so its registry evidence state cannot be decided from assumption.

## Verification

The plan is complete when every discovered modelo has an explicit, digest-pinned inventory outcome; the M130 external blank candidate reaches the production extraction primitives without producing any fabricated monetary value; the blank-box regression is proven to bite; provenance claims are limited to observable physical facts and source-chain evidence; M130's registry and operator-facing evidence status matches the measured result; the focused declaration parser, extraction-profile, provenance and reconciliation-advisory unit modules pass; and the mandatory fresh-context code review records no unresolved high or critical finding.
