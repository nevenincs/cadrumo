---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:dc947483e26b2fe5882d348dc878aec2353eb00d9d58f508602179b1721a30c0'
step_id: 'S17'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Adjudicate Modelo 187 revision 2019-y-siguientes design-era coverage

## Scope

- `.vault/reference/`

## Description

- Re-fetch the BOE sources which change Modelo 187 record fields for 2020, 2021, and 2022.
- Re-fetch AEAT's current design catalogue and Modelo 187 filing surface.
- Compare those sources with the hash-pinned 2022 design, the selected source era, casillas, producer vocabulary, and worklist.
- Record the refusal, owners, and reconsideration gates without production changes.

## Outcome

Modelo 187 remains applicability-only and non-fileable for every selected year. The current AEAT 2022 design is valid post-2022 evidence but cannot cover 2019--2021, which BOE shows contains real design changes. The revision also lacks the type-1/type-2 producer contract, semantic map, layout, generated tree, and emitted-byte proof. The 2019+ Article 2 filing population has two limbs: the withholding/pay-on-account payer limb and the separate Article 42 RGAT person/entity limb for IIC operations. The latter remains incomplete in the present one-fact applicability selector; it was not and must not be treated as a withholding-only population.

`W02.P04.S26` owns exact historical source eras and any split. `W02.P04.S28` owns producer assignment and export proof. The reference records official URLs, hashes, boundaries, and reconsideration conditions.

## Notes

- Focused committed-registry and source-grounding tests were run; they passed before the shared execution reached its reporting timeout.
- The aggregate filing-capability worklist failed as designed and named `187/2019-y-siguientes` blocked on 2019--2021 design coverage. This is the asserted refusal, not a regression.
- An early uncommitted reference draft encountered a shell encoding issue. The final reference was regenerated through the vault CLI and re-attested as UTF-8; no other file was changed to correct it.
- S78 corrected the Article 2 population after independent review against BOE-A-2018-17997 and the bundled/current RGAT Article 42 text. This clarification neither adds a filing route nor changes the applicability-grade refusal.
