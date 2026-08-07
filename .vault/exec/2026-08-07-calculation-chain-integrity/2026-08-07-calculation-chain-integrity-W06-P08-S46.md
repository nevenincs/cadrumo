---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e4ea057ae82b9da3d2e7f12a850bc1ee725d4e0ede27f37b3547f11b428566e4'
step_id: 'S46'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S46

## Outcome

**Neither, and the answer is more useful than either.** The four categories are not missing from the annual form, and they are not settlement lines the registry dropped. They sit on a **different axis** of the annual form that the registry does not model at all.

## The four, measured rather than assumed

Comparing the ledger-IVA categories each side's bound casillas select, from the loaded snapshots:

- Modelo 390: 6 categories across 22 casillas (16 carrying a binding)
- Modelo 303: 10 categories

Exactly four are on the quarterly side with no annual counterpart, which matches the Step's count:

    domestic_reverse_charge
    export_assimilated_zero_rated
    export_third_country_zero_rated
    intra_community_supply

## Where they actually live on the official annual form

Searched the bundled 2024 M390 diseño. All four concepts ARE present — in **section 10, "Volumen de operaciones"**:

    [Pág. 6]  10. Volumen de operaciones - Entregas intracomunitarias de bienes y servicios  [103]
    [Pág. 6]  10. Volumen de operaciones - Exportaciones y otras operaciones exentas con derecho a deducción
    [Pág. 6]  10. Volumen de operaciones - Operaciones sujetas con inversión del sujeto pasivo  [125]

Section 10 is a **turnover disclosure**, not a liquidación section. It reports what the taxpayer did over the year; it does not compute devengado or deducible from it.

Reverse charge additionally has one genuine annual settlement line, but under a regime the registry does not model:

    [Pág. 5]  6. Operaciones Reg. Simplificado - IVA devengado por inversión del sujeto pasivo  [1084]

## What this means for each reading the Step offered

**"Correct by the annual form's own design"** — true of the *settlement spine*. The annual return does not carry per-category export or intra-community devengado lines the way the quarterly return does, so the registry's 22 casillas are not silently dropping settlement figures. A reader comparing the two category sets and concluding the annual side under-declares would be wrong.

**"A registry-completeness gap"** — true of a *different thing*. Section 10 volumen de operaciones is entirely unmodelled, and it is where these four concepts are annually reported. That is a real gap, just not the one the category comparison appears to show.

## Why keeping them apart matters

Collapsing to either answer produces a wrong next action. "By design, nothing to do" leaves an unmodelled official section invisible. "Completeness gap, add the categories" would add devengado bindings for boxes the annual liquidación does not have, inventing settlement lines from a turnover section.

The actionable residue is therefore section 10 rather than the four categories, and it belongs to the scoping `W06.P08.S47` performs.

## Note on the parity gate

This is also why the reconciliation parity gate compares only the shared-role intersection and says so: a concept present on one side as settlement and on the other as turnover is not a parity divergence, and forcing it into the comparison would fire on a difference the official forms intend.
