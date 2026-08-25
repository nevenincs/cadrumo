---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:cdc8ad48de4769491e594da7b3d697008e25127386b3451c595d05aa2c00cb3b'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` audit: `S233 M194 no-candidate review`

## Scope

Independent review of `eff00904fd`: finite M194 designs, manual summaries,
withholding non-substitutability, factual research, and no-promotion boundary.

## Findings

### exact eras | low | three AEAT designs match their selected years

The 2019, 2023, and 2024 AEAT design hashes recompute to
`792cd3ab3f1e94ce7afd62a6fa37710253aec7b801e3097ad27741f90a657d5a`,
`83cd9a332e0016607e87332bea8c3e5d33f0b0f8373ec56f820d82414ca76a7b`, and
`4a738a126ddb465aac236b687aa25441b7cb71ec4b0ef6ea940096a3747b2651`.
Selectors refuse 2020--22 and 2025 onward.

### source boundary | low | manual summaries and withholding are non-substitutable

Each selected revision has five direct manual summaries and no bindings,
formulas, extraction profiles, layouts, source owner, resolver, producer, or
census row. M190/M193 withholding lacks M194 ORIGEN, asset acquisition and
transmission semantics, signed base, and per-operation row identity, so cannot
be promoted as an M194 source.

### governance | low | no ADR or runtime promotion is warranted

Research is factual-only and frames no current candidate without declaring tax
facts inapplicable. The accepted framework governs a future candidate; no
census or runtime change occurred.

### verification | low | focused gate is green

M194 registry coverage passed 15 tests and Ruff passed.

## Recommendations

PASS. Preserve the finite eras and direct manual path. Reopen only with an
official source fact and holder, exact type-1/type-2 destination map, lossless
encrypted lifecycle, and separate export proof.

