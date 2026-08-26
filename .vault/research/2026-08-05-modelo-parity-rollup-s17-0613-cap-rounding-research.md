---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:b6e26255c30914c83fe4b8dd0625ae807ea6629e5d72665e0140eccb15c733b5'
related:
  - "[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]"
  - "[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]"
---
# `modelo-parity-rollup` research: `S17 0613 cap and rounding evidence`

The evidence-only S17 addendum does not support promoting Modelo 100/2025 casilla `0613`: the official sources establish the qualifying population and effective-spend limit, but their published worked examples do not expose one executable rounding rule for partial-month caps. The safe next gate is an authoritative per-child cap/rounding oracle plus a real profile-to-calculate matrix; the 2025 row remains manual until that gate is closed.

## Findings

### The 2025 legal contract is per-child, month-qualified, and based on effective non-subsidized spend

The bundled Renta 2025 manual defines custody expenses as pre-registration and matrÃƒÂ­cula, attendance, and food paid for complete months, excludes exempt employer in-kind amounts, and extends the turning-three period only for post-birthday expenses through the month before the second cycle may begin (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54765-54880`). It states an increase of up to `83.33` euros per qualifying month and a per-child annual limit of `1,000` euros (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54863-54916`). It separately defines the annual effective non-subsidized spend limit, including amounts paid by both parents and subtracting subsidies and exempt employer payments (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54884-54904` and `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:55010-55022`). The official 2025 help page confirms the same two limits and the both-parent effective-spend rule: https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2025/8-cumplimentacion-irpf/8_8-cuota-diferencial-resultado-declaracion/8_8_2-resultado-declaracion/8_8_2_1-deduccion-maternidad/guarderia.html.

The consequence for the producer contract is load-bearing: the correct value is a sum of per-child minima, not `min(total spend, total child cap)`. Two children with unequal qualifying-month counts can produce a different result from an aggregate minimum. A 2025 profile must therefore carry, or canonically derive, each child's complete-month population and effective annual spend. The current aggregate paths do not provide that contract (`src/cadrumo/application/modelo/_profile_binding.py:235-286`; `src/cadrumo/domain/contribuyente/family.py:984-1060`; `src/cadrumo/domain/contribuyente/family.py:1373-1398`).

### Official examples leave the rounding stage unresolved

The 2025 manual reports `1,000 / 12 Ãƒâ€” 2 = 166.67` and `1,000 / 12 Ãƒâ€” 6 = 500` (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54989-55004` and `:55073-55088`). Those examples are compatible with retaining full precision through the multiplication and rounding the result to cents. They do not settle seven, eight, or twelve qualifying months.

Official AEAT worked examples expose a conflicting observable rule. The 2021 example reports eight qualifying months as `666.64` (https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2021/capitulo-18-cuota-liquida-cuota-autoliquidacion/resultado-declaracion/deduccion-maternidad-incremento-adicional-gastos-custodia/ejemplo-deduccion-maternidad-incremento-gastos-custodia.html). The official 2022 FAQ reports seven months as `583.33` (https://sede.agenciatributaria.gob.es/Sede/ayuda/renta-preguntas-frecuentes/renta-2022-preguntas-frecuentes/ejemplo-hijo-asistio-guarderia-ejercicio-antes.html), and its continued-attendance example uses the same `83.33` monthly explanation (https://sede.agenciatributaria.gob.es/Sede/ayuda/renta-preguntas-frecuentes/renta-2022-preguntas-frecuentes/ejemplo-hijo-sigue-asistiendo-guarderia-anos.html).

The competing executable interpretations are materially different:

- Displayed monthly amount `83.33` multiplied by months gives `666.64` for eight, `583.31` for seven, and `999.96` for twelve.
- Exact `1,000 / 12` retained through the total and rounded once gives `666.67` for eight, `583.33` for seven, `166.67` for two, and `1,000.00` for twelve.
- An annual cap of `1,000` alone resolves twelve months but does not define partial-month results.

The published `666.64` and `583.33` observations cannot both be produced by one of those simple stages. The evidence therefore establishes a genuine authority discrepancy, not a safe implementation choice. The `money-2` rounding marker on the existing 2024 formula is not sufficient evidence for 2025, and the 2024 `cotizaciones_ss_madre_2024` term must not be reused (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0181-renta-2024-incremento-guarderia-0613.toml:1-21`).

### The current profile surface cannot yet express the 2025 producer

The 2025 schema declares `0613` as a manual casilla with legal and form sources and no formula back-reference (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8`). The user-profile schema exposes year-parameterized raw guarderí spend and population selectors, but the only Social Security field is explicitly 2024-specific (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:19-55` and `:1651-1657`). The canonical family record has annual and sparse monthly raw spend, but no explicit versioned effective non-subsidized per-child amount or per-child cap result (`src/cadrumo/domain/contribuyente/family.py:151-177` and `:303-314`).

Adding only three 2025 registry rows would therefore create a producer whose input contract cannot distinguish parent-paid totals, subsidies, exempt employer payments, unequal child caps, or unresolved annual-only month counts. Cloning the 2024 formula would also falsely carry the 2024-only Social Security fact into 2025. Both alternatives are rejected by the existing S17 evidence boundary (`.vault/research/2026-08-05-modelo-parity-rollup-s16-s18-evidence-research.md:32-42`; `.vault/exec/2026-08-05-modelo-parity-rollup/2026-08-05-modelo-parity-rollup-W03-P08-S17.md:18-28`).

### Required independent oracle matrix before SOL can authorize promotion

The next evidence addendum must carry independent expected values and real profile-to-calculate coverage for: twelve qualifying months; two, six, seven, and eight months at the competing rounding boundaries; spend below the statutory monthly cap; spend above the month-derived cap; effective spend reduced by subsidies and exempt employer payments; zero spend; a child turning three with only post-birthday months; and two children with unequal qualifying-month caps. The matrix must keep raw spend, effective spend, qualifying-month count, per-child capped amount, and final `0613` value distinct. It must also prove the reverse schema invariant once a producer is eventually authorized: `0613` is `computed`, its formula ID is the formula's target, and every formula binding is declared and resolved.

Until the authority discrepancy is resolved, a domain test may exercise the existing real monthly filtering and raw-spend path, but it must not present that prerequisite behavior as a `0613` calculation oracle. This boundary is the SOL adjudication recorded for S17, and it keeps the 2025 row manual rather than manufacturing a value from an unresolved rule.

## Sources

- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:54765-55022`
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md:58777-59042`
- `src/cadrumo/domain/contribuyente/family.py:151-177`
- `src/cadrumo/domain/contribuyente/family.py:303-314`
- `src/cadrumo/domain/contribuyente/family.py:984-1060`
- `src/cadrumo/domain/contribuyente/family.py:1373-1398`
- `src/cadrumo/application/modelo/_profile_binding.py:235-286`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:19-55`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1651-1657`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/0181-renta-2024-incremento-guarderia-0613.toml:1-21`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8`
- `.vault/research/2026-08-05-modelo-parity-rollup-s16-s18-evidence-research.md:32-42`
- `.vault/exec/2026-08-05-modelo-parity-rollup/2026-08-05-modelo-parity-rollup-W03-P08-S17.md:18-28`
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2025/8-cumplimentacion-irpf/8_8-cuota-diferencial-resultado-declaracion/8_8_2-resultado-declaracion/8_8_2_1-deduccion-maternidad/guarderia.html
- https://sede.agenciatributaria.gob.es/Sede/ciudadanos-familias-personas-discapacidad/deducciones-relacionadas-hijos-descendientes/deduccion-maternidad/incremento-deduccion-maternidad-gastos-guarderia.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2021/capitulo-18-cuota-liquida-cuota-autoliquidacion/resultado-declaracion/deduccion-maternidad-incremento-adicional-gastos-custodia/ejemplo-deduccion-maternidad-incremento-gastos-custodia.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/renta-preguntas-frecuentes/renta-2022-preguntas-frecuentes/ejemplo-hijo-asistio-guarderia-ejercicio-antes.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/renta-preguntas-frecuentes/renta-2022-preguntas-frecuentes/ejemplo-hijo-sigue-asistiendo-guarderia-anos.html

## S32 acquisition attempt (2026-08-05)

This evidence-only acquisition used VaultSpec-RAG before source inspection. The directed grounding recalled the accepted parity ADR, the S17 evidence boundary, the current 2025 profile and casilla surfaces, and the existing real-behavior tests. The official AEAT 2025 pages were then checked for an executable cap-and-rounding matrix.

The official 2025 material establishes:

- the increment can reach `83.33` euros per qualifying month and has a `1,000` euro annual limit per child;
- the official two-month worked example reports `1,000 / 12 x 2 = 166.67`;
- the official six-month worked example reports `1,000 / 12 x 6 = 500`;
- the filing guidance places the resulting amount in casilla `0613`.

The checked official pages are:

- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c18-cuota-liquida-resultante-autoliquidacion/resultado-declaracion/deduccion-maternidad-incremento-adicional-gastos-custodia/incremento-adicional-gastos-custodia-guarderias/cuantia-incremento-adicional.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c18-cuota-liquida-resultante-autoliquidacion/resultado-declaracion/deduccion-maternidad-incremento-adicional-gastos-custodia/ejemplo-deduccion-maternidad-incremento-gastos-custodia/caso-a-alta-ss-posterioridad-nacimiento.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c18-cuota-liquida-resultante-autoliquidacion/resultado-declaracion/deduccion-maternidad-incremento-adicional-gastos-custodia/ejemplo-deduccion-maternidad-incremento-gastos-custodia/caso-b-cobro-prestacion-desempleo-subsidio.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2025/8-cumplimentacion-irpf/8_8-cuota-diferencial-resultado-declaracion/8_8_2-resultado-declaracion/8_8_2_1-deduccion-maternidad/guarderia.html

The complete S32 matrix was not acquired. The 2025 publications do not provide independent expected `0613` outputs for the seven-, eight-, and twelve-qualifying-month rounding boundary, or the required combinations of spend below and above the cap, subsidies and exempt employer payments, both-parent payment, turning-three timing, and unequal qualifying-month caps for two children. The published two- and six-month observations do not resolve whether the annual fraction is retained through the final rounding stage or a displayed monthly amount is multiplied; the existing cross-year `666.64` and `583.33` observations remain an authority discrepancy rather than a safe 2025 rule.

S32 remains open. No registry, formula, binding, relation, profile, application, or test producer was changed, and no value was enrolled as a `0613` oracle. The next admissible action is an independent executable oracle acquisition or a new SOL ruling that explicitly resolves the rounding and per-child matrix.

## Live AEAT 2025 executable oracle addendum (2026-08-05)

The static-only conclusion above is superseded for the cap, per-child aggregation, rounding, and post-third-birthday timing questions by an independent live calculation run on the official AEAT Renta WEB Open simulator. The evidence was acquired with VaultSpec-RAG first: request 16afa387a55842ea8bb39547a7d35b67 returned S30, S17, S28, and S32; the earlier code-grounding request 22fbeb304c5a4ce28298f1843c4a1d5e located the current profile, registry, and application surfaces.

The simulator URL was:
https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?EJER=2025&TACCESO=COLAB

The official help entry describing this unauthenticated simulator is:
https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-web-open.html

All data in this run was synthetic audit data. No declaration was presented or exported. The simulator was used only through the real Modelo 100 maternity and guarderia calculation path. Its displayed official clock was 05/08/2026 19:04:13-19:04:39 for the two-child run and 05/08/2026 19:12:31-19:13:26 for the post-birthday run.

### Live matrix

The guarderia input was the simulator's effective non-subsidized amount field. A 2,000.00 amount was therefore an above-cap effective amount; a 100.00 amount was below the two-month statutory cap. No subsidy or exempt employer payment was entered in this run.

| Case | Effective spend | Qualifying complete months | Child result | Final 0613 |
| --- | ---: | ---: | ---: | ---: |
| zero / blank | blank | 0 | blank, semantic zero | blank, semantic zero |
| below cap | 100.00 | 2 | 100.00 | 100.00 |
| above cap | 2,000.00 | 2 | 166.67 | 166.67 |
| above cap | 2,000.00 | 6 | 500.00 | 500.00 |
| above cap | 2,000.00 | 7 | 583.33 | 583.33 |
| above cap | 2,000.00 | 8 | 666.67 | 666.67 |
| above cap | 2,000.00 | 12 | 1,000.00 | 1,000.00 |

These rows are consistent with 1,000 / 12 retained at full precision through the annual multiplication and rounded once to cents. They are not consistent with multiplying a displayed 83.33 monthly amount, which would produce 666.64 for eight months.

### Unequal child caps and a child turning three in 2025

A two-child run used child A born 01/01/2023 with 2,000.00 effective spend and two selected months, and child B born 31/12/2022 with 2,000.00 effective spend and six selected months. Child B's maternity dialog reported 11 qualifying maternity months because the child turned three during 2025. The per-child guarderia results were 166.67 and 500.00, and the live final 0613 was 666.67. This is an executable observation of per-child aggregation with unequal caps; it is not a total-spend aggregate minimum.

### Post-third-birthday-only month

A second run used child B born 01/01/2022, so the child had already turned three at the start of 2025. Only February was selected in the guarderia dialog, with 2,000.00 effective non-subsidized spend. The live child result was 83.33. Child A remained at 166.67 for two months, and the live final 0613 was 250.00. This demonstrates that a complete month after the child turned three can contribute to the guarderia increment in the live 2025 surface.

### Interpretation and residual boundary

The live official oracle closes the earlier 2025 rounding uncertainty and provides real profile-to-calculate evidence for zero, below-cap, above-cap, 2/6/7/8/12-month, unequal-two-child, and post-third-birthday cases. It does not close every input-contract dimension required for schema promotion: this run did not enter separate parent-paid amounts, subsidies, exempt employer payments, or a second person with the right to the deduction. The simulator also disabled the multiple-right-holder controls for the synthetic single declarant with ordinary child linkage. Those dimensions remain an evidence gap, not an inferred zero.

The resulting producer contract remains per-child: for each child, resolve effective annual spend and the eligible complete-month population, apply the annual-per-child cap, retain the exact 1,000 / 12 fraction, round the per-child result to cents as observed by the oracle, then sum child results into 0613. Promotion still requires SOL to decide whether the live surface is sufficient for the remaining effective-spend and multi-right-holder contract, and no 2025 registry, formula, binding, relation, profile, application, or test producer was changed by this addendum.
## Binding SOL ruling and S32 closeout (2026-08-05)

The earlier static-only conclusion and the live-oracle residual boundary above are historical evidence notes. SOL now rules: APPROVE S32 closure strictly as authoritative oracle acquisition. No further rows are required to close S32 numeric oracle acquisition. This closes the W06.P13.S32 evidence gate only; it does not close W03.P08.S17 semantic adjudication or authorize any 2025 `0613` producer promotion. All 2025 producer promotion is DEFERRED, with no external-grounding enrollment.

The ruling was grounded with VaultSpec-RAG request IDs `51ae4d3c659242ffb025ca2516611737` and `2e292d0a3ae2427d8a555aa75d6810b1`. The accepted vault search mode was available, so this record retains the service-backed discovery trace. The service reported index integrity as unverifiable because no claim was returned; this discovery result is grounding input, not proof.

### Accepted S32 numeric oracle rows

The live AEAT values now accepted for the S32 acquisition are:

- blank expense with zero selected months: blank, semantic zero;
- `100 / 2 = 100.00`;
- `2,000 / 2 = 166.67`;
- `2,000 / 6 = 500.00`;
- `2,000 / 7 = 583.33`;
- `2,000 / 8 = 666.67`;
- `2,000 / 12 = 1,000.00`;
- unequal children: `166.67 + 500.00 = 666.67`;
- post-third-birthday child with one qualifying month: `83.33 + 166.67 = 250.00`.

The rows establish the observed numeric rule for this evidence gate: retain exact `1,000 / 12` through per-child multiplication, round each per-child result to cents, and sum the per-child results. They close S32 numeric oracle acquisition without enrolling a registry value or changing production wiring.

### Runtime discrepancy retained honestly

The 2025 registry cap parameter is `None`; qualifying months are `1`; maternity months are `0`; the current helper result is `0`; and the live AEAT result is `83.33`. This exposes a dormant deficiency in the current runtime. It is not a wiring authorization and must not be converted into a fallback, silent under-declaration, or compatibility path.

### Minimum pre-promotion oracle remains deferred

Before any 2025 producer promotion, the remaining minimum oracle is:

1. A non-degenerate effective-spend row with parent-paid amount, public subsidy, and exempt employer contribution, with net effective spend below the cap.
2. An enabled multiple-right-holder allocation.
3. Disjoint maternity and guarderia months.
4. A partial overlap where count-minimisation differs from month-set intersection.
5. After source-contract implementation, a bundled Renta WEB Open replay plus an independent real secure-profile-to-registry-engine reproduction.

Until those gates are acquired, the 2025 row remains manual and no external-grounding enrollment is allowed.

### Plan and reverse-invariant boundary

The resulting plan state is `29/32`: S16 is `OPEN/DEFERRED` with 0150 manual, S17 is `OPEN/DEFERRED`, S18 is `OPEN/DEFERRED`, and only S32 is `COMPLETE` after its execution record is updated. Any eventual producer must satisfy the reverse invariant: the casilla is computed, the casilla and formula target carry the identical formula ID, every binding is declared and resolved with provenance, and an independent real-runtime replay passes. No schema, formula, binding, relation, profile, persistence, application, test, corpus-enrollment, or IRP invocation-shape file is changed by this ruling.
