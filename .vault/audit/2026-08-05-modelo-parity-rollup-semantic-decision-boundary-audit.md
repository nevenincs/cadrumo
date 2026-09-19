---
tags:
  - '#audit'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:6db1656577931c8a4f74f82a831536f2e1b5425a3b839487db2af0f9f7a4fe1c'
related:
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-denominator-research]]"
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# `modelo-parity-rollup` audit: `Modelo parity rollup semantic decision boundary`

## Scope

Adjudicate the three deferred Modelo 100/2025 semantic rows that showed the largest cross-revision producer drift: casillas `0150`, `0613`, and `1481`. The decision boundary covers schema declaration, producer wiring, profile/runtime evidence, legal/source evidence, and the evidence required before a manual row can become computed or upstream.

The review used VaultSpec RAG over the accepted parity ADR, research, plan, registry declarations, producer analogues, profile paths, and existing runtime tests. The current worktree contains no semantic-row production change.

## Findings

### Modelo parity rollup semantic decision boundary | medium | 0150 remains manual in 2025

The 2025 `0150` row has no `input_kind`, `formula`, or `binding`, so it is manual by schema default. The 2025 revision has no formula targeting it; the `0154` formula only consumes it. The 2024 analogue is a computed, reverse-wired Art. 23.2 producer with a year-specific selector and worked example. That evidence cannot be copied into 2025 because the 2025 selector, parameters, contract-date transitions, and independent numeric oracle were not established.

SOL's second adjudication retains `0150` as manual and leaves S16 open. The smallest remaining gates are canonical persisted finca/contract facts with bucket identity, fingerprints and provenance; a typed enrolled source resolver; an explicit per-inmueble/per-contract allocation contract covering qualification, negative yields, rounding and carry-forward; one producer mechanism with exact reverse wiring; and a structured official 2025 oracle reproducing the manual's `1,717.50` and zero-reduction outcomes through the real secure-storage-to-calculate path.

### Modelo parity rollup semantic decision boundary | medium | 0613 remains manual in 2025

The 2025 `0613` row has no producer declaration or reverse wiring; the final-settlement formula only subtracts it downstream. The application has a real, year-parameterized guardería profile path and the existing worked examples prove 2024 monthly transport and cap behavior, but the 2025 registry declares none of the required bindings and the contribution fact remains year-specific to 2024. Structural application support is not 2025 producer evidence.

SOL's second adjudication retains `0613` as manual and leaves S17 open. It rejects carrying forward the 2024 cotizaciones ceiling without authoritative 2025 evidence. Reopening requires a corrected 2025 Art. 81.2 contract for eligible months, turning-three treatment, beneficiary eligibility, subsidies, employer-exempt payments, effective expenditure, proration and rounding; versioned child/month/net-expenditure facts; one authoritative producer mechanism; exact profile selectors, bindings, formula target and reverse casilla reference; and structured official-oracle cases for the `166.67`, `500.00`, zero and turning-three outcomes.

The Luna prerequisite oracle is now present at `src/cadrumo/domain/contribuyente/tests/test_guarderia_2025_facts.py`. It exercises the real 2025 family aggregation for full-period monthly spend (`1,800`), turning-three post-birthday-month spend (`1,600`), and a non-qualifying child (`0`). This is source capability evidence only; it does not promote 0613 or establish the final statutory cap.

### Modelo parity rollup semantic decision boundary | medium | 1481 remains manual in 2025

The 2025 `1481` row has no formula or binding. Its downstream formula carries the value into `1482`, but downstream consumption is not production. The 2024 live path proves a relation-prefill sum from quarterly M131 `01` into M100 `1481`; it uses seeded 2024 values and does not establish 2025 period semantics. The 2025 M131 relation found in the registry targets payments, not `01` into `1481`.

SOL's second adjudication retains `1481` as manual and leaves S18 open. The proposed four-quarter M131 sum is rejected because it can multiply an annual basis and loses activity identity. Reopening requires authoritative 2025 annual M100 módulos semantics; an activity-preserving contract covering multiple activities, seasonal operation, commencement and cessation; an explicit distinction between per-activity `1481` and aggregate `1482`; a canonical relation only if official evidence proves the transfer; exact reverse wiring; and an independent 2025 M131/M100 runtime oracle.

### Modelo parity rollup semantic decision boundary | low | The no-change boundary is intentional

The absence of 2025 producers is a measured divergence, not an omission to be repaired by cloning the previous revision. The accepted parity contract requires exact law-selected revision evidence, typed producer ownership, construct-level source proof, canonical handoff semantics, and independent runtime values before a manual row can be reclassified.

## Recommendations

Keep S16, S17, and S18 open and retain the 2025 manual declarations. Do not add formulas, bindings, selectors, parameters, profile facts, relations, or cross-model aggregation until the row-specific evidence lists above are complete and SOL re-adjudicates the result. Report any future claim as deferred rather than as parity passed until independent 2025 numeric evidence exists.

## Verification boundary

- The generic all-registry formula-target reverse invariant remains enforced by `src/cadrumo/domain/calculations/registry/_validate_formulas.py` and its registry test suite.
- The bounded M100 2025 semantic guard remains green for `0150`, `0613`, and `1481`.
- The new Luna oracle test passes `3` focused cases; it is intentionally not a schema promotion test.
- No production registry, fincas source, family profile, M131 relation, formula, binding, casilla, or aggregation change is authorized by this adjudication.
