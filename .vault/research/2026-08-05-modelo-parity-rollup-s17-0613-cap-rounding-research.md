---
tags:
  - '#research'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c953763d377c3c768b81b0a665979e5fdc944691cf08f76c4a4fc5bfc9e9789f'
related:
  - "[[2026-08-05-modelo-parity-rollup-s16-s18-evidence-research]]"
  - "[[2026-08-05-modelo-parity-rollup-s16-s18-candidate-contract-matrix-research]]"
  - "[[2026-08-05-modelo-parity-rollup-W03-P08-S17]]"
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

The 2025 schema declares `0613` as a manual casilla with legal and form sources and no formula back-reference (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/casillas/0194-c0613.toml:1-8`). The user-profile schema exposes year-parameterized raw guarderÃƒÂ­a spend and population selectors, but the only Social Security field is explicitly 2024-specific (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:19-55` and `:1651-1657`). The canonical family record has annual and sparse monthly raw spend, but no explicit versioned effective non-subsidized per-child amount or per-child cap result (`src/cadrumo/domain/contribuyente/family.py:151-177` and `:303-314`).

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
