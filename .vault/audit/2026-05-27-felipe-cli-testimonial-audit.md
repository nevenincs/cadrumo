---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-olivia-cli-testimonial-audit]]"
  - "[[2026-05-27-khadija-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-26 Felipe Aragoneses pensionista español Argentina IRNR`

## Scope

Twenty-sixth testimonial round, Felipe Aragoneses Cebrián — 68,
retired civil engineer, Argentine fiscal resident since 2018,
Spanish nationality + Spanish-state pension (€36k MUFACE retención
7% Art. 25.1.b TRLIRNR) + small private pension (€3.5k retención
24%) + vacant vivienda Madrid (Art. 13.1.h imputación rentas
inmobiliarias non-resident). Exercises Spanish-pensioner-abroad
surface + Convenio España-Argentina BOE-A-1994-22783.

## Findings

### CRITICAL P0 — S176 regression `aeat config *` bricked

Filed as #228. S176 commit `dc4f07386` introduced wizard
`situacion-familiar` question without the matching
`_SETUP_OPTION_INFOS` dict entry. `KeyError` raised at module
import time — bricks every `aeat config *` subcommand. Felipe
re-confirms across multiple personas (Inés, Diego, Khadija
previously hit transient equivalents).

### CRITICAL — M210 stub re-confirms #196

M210/M211/M216/M296 entirely absent from registry. No IRNR
coverage for non-residents. Filed under #196 stub bundle
(in flight via one-shot a2d34063eb7128c26).

### CRITICAL — Art. 13.1.h TRLIRNR imputación rentas vivienda vacía non-resident

For non-resident owner of Spanish vivienda no arrendada,
Art. 13.1.h applies fictional rent (2% × valor catastral, or
1.1% if catastral revised < 10 years). M210 quarterly clave
R (rendimiento bienes inmuebles no arrendados). The CLI has
no axis for non-resident inmuebles + no M210 channel.

### HIGH — Art. 25.1.b TRLIRNR tipo especial pensión pública

Spanish-state pensions to Spanish nationals abroad tributan
exclusively in Spain at the Art. 25.1.b special tipo (7% on
gross MUFACE pension). The CLI applies IRPF progressive tariff
instead — wrong régimen for non-residents entirely.

### HIGH — Convenio España-Argentina absent

BOE-A-1994-22783 Art. 19.1 (pensiones públicas) requires Spain-
side IRNR taxation. The CLI lacks convenio Argentina entry +
non-resident axis to invoke it. Re-confirms #198 territory.

### HIGH — Non-resident axis re-confirmed (#197)

Profile only accepts Spanish CCAA. No `--tax-residence-country
-code AR`. Profile silently defaulted Felipe to `madrid` — same
gap surfaced by Olivia (UK) + Khadija (MA).

## Recommendations

1. **#228 (P0)** — fix wizard regression immediately.
2. **#196 stub bundle** — already in flight, includes M210.
3. **#197 non-resident axis** — already pending; this round
   raises priority further.
4. **#198 Convenio extension** — Argentina + Morocco + UK
   + ... lookup table.
5. **Art. 25.1.b special tipo** — new task: state-pension non-
   resident path (7% vs 24% general).
6. **Art. 13.1.h non-resident vivienda imputación** — new task
   under M210 engine wave.
