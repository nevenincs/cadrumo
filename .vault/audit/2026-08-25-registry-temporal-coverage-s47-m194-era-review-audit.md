---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:575ec560979a1e65341bb2118b4228c03e7257e1c65cf6dc160c3d5a82918a44'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-temporal-coverage-W02-P05-S47]]'
---

# `registry-temporal-coverage` audit: `S47 Modelo 194 design-era review`

## Scope

Independent review of `8824172d838` and `7665546e08d`, their S47 execution record, the temporal plan and M194 evidence, the legal/source catalogue, all three revision trees, corpus manifest, locale catalogues, and focused tests.

## Findings

### s47-era-authority | low | the three selected eras are exact and finite

Modelo 194 selects only `2019`, `2023`, and `2024`; each revision has matching finite validity and annual selector bounds, exactly one matching `aeat-dr-194-*` source, and the applicable BOE amendment plus commencement reference. 2020--2022 and 2025 onward refuse.

### s47-corpus-integrity | low | source catalogue and corpus hashes agree

The 2019, 2023, and 2024 design binaries match their manifest and catalogue SHA-256 declarations. The 2024 source ends at 2024-12-31, and the mutation proof rejects an attempted 2025 selector expansion through the shared source resolver.

### s47-capability-boundary | low | no output authority was introduced

All three revisions remain applicability grade with manual casillas and no export layouts. There is no Modelo 194 filing-producer namespace, semantic map, render profile, or duplicate selection authority.

## Recommendations

Retain the finite selectors and source-window mutation proof. Any future Modelo 194 exercise requires its own exact hash-pinned source, legal applicability evidence, and separately completed output-capability chain.
