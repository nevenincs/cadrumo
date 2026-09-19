---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e3664ed2e23c1a261bd317fbcff61a13e5ed7e8e9eb84164ac82537b85e2f7d5'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `Modelo 187 filer population review`

## Scope

Independent post-review of `49e7f903f2`, limited to Modelo 187's official design-era evidence, 2022 source scope, 2019--2021 and post-2022 coverage, filing population, refusal posture, owner routing, and execution-record accuracy.

## Findings

### modelo-187-article-2-population | medium | The adjudication omits an independent filer population

The new reference says that Modelo 187 requires the filer to be a person obliged to withhold or pay on account. Article 2 of BOE-A-2014-9225 contains that limb, then separately makes the persons or entities referred to in Article 42 of the RGAT obliged for IIC operations. Collapsing the two into a withholding-only criterion makes the stated filing population narrower than the governing text. The current applicability-only, no-layout refusal remains correct: the issue is the exact prerequisite that would be evaluated before any future filing-grade decision, not a reason to promote the revision.

The remaining evidence is accurate. BOE-A-2020-17271 adds the type-2 payment-on-account field at position 241 for the 2020 declaration; BOE-A-2021-20004 adds key K at position 142 for 2021; and BOE-A-2022-14168 changes position 104 and adds positions 242--250 for 2022. The bundled 345403-byte, `c7a21c1feb9619380bb0da3e73066fa3c58c628f430bf85ed9dbea15b1308eb1` AEAT design is explicitly current-catalogue evidence updated for exercise 2022 and the registered source begins in 2022 with no closing date. It supports the refusal of 2019--2021 coverage and does not authorize a layout. The current AEAT procedure page provides current 2025 filing and historical 2020--2024 routes, which proves a live surface but not historical layout equivalence.

## Recommendations

- `W02.P04.S78` must correct the S17 reference and execution record to state both Article-2 filer limbs, retain applicability-only and non-fileable status, and require an approved population decision covering each relevant limb before a filing-grade promotion.
- Keep the existing non-overlapping routes: `W02.P04.S26` for exact official temporal eras and any selection split, and `W02.P04.S28` for producer assignment, reviewed map, canonical generation, rendering, and emitted-byte proof.
