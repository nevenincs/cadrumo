---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:2dfcc8ae788888b4570da452084f2d529af00f7799ebef51e9684336b0d23f06'
step_id: 'S08'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
---

# author the complete M210 casilla set on the 2025 revision with completeness manifest, extraction-profile targets, and export parity, with casilla count and numbering taken from the fetched layout authority

## Scope

- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas`

## Description

- Renumber the seven existing base/rate/cuota boxes to their official numbers taken from the S07 layout authority: `rendimientos_integros`=`[5]`, `gastos_deducibles`=`[7]`, `base_imponible`=`[8]`, `tipo_gravamen`=`[21]`, `cuota_integra`=`[22]`, `retencion_practicada`=`[29]`, `cuota_diferencial`=`[31]`.
- Author the remaining official numbered boxes `[4]`,`[6]`,`[9]`-`[20]`,`[23]`-`[28]`,`[30]` in a companion casilla fragment `0002-casillas-diseno-registro.toml`; the four inmobiliaria-support inputs keep their engine-internal identifiers as they are not `[4]`-`[31]` numbered boxes.
- Add the liquidación formula chain as registry formulas: `[17]=[12]+[16]` (ganancias base), `[24]=[22]-[23]` (cuota Ley IRNR), `[28]` = clamped convenio reduction (`min([24],[26])` when a límite convenio is declared, else `[24]`), `[27]=[24]-[28]` (reducción por convenio), and rewire `[31]=[28]-[29]-[30]` (resultado).
- Update the completeness manifest to the recomputed calculation closure, add the four new formulas to the M210 IRNR construct, and extend legal/source grounding with the S07 layout authority.
- Add a structural + formula-wiring parity test that asserts every official `[4]`-`[31]` number is declared and that the declared arithmetic evaluates end-to-end on worked inputs across the no-convenio, convenio-clamp, ganancias, and complementaria paths.

## Outcome

All official `[4]`-`[31]` boxes are declared; the registry loads; the full liquidación chain evaluates correctly. The 107 prior Modelo 210 tests pass unchanged (the no-convenio path collapses to the pre-slice cuota-minus-retenciones result), the 6 new parity tests pass, and the record-design/completeness/export/corpus/hygiene gates pass. `ruff`, `ruff format`, and `ty` are clean. Committed as `a9d7002f28`.

## Notes

Deferred and documented in file comments: the exención-dividendos `[6]` subtraction into the type-R base op is not wired (dividends currently route through the Art. 25.1.f 19% branch, not the rendimientos-R deduction path), so `[6]` is authored as the official input field only; the type-I `[4]` and type-G `[18]` direct-base boxes are operator inputs, and `[27]` is derived from the clamped `[28]` rather than computed as an unconditional `[24]-[26]` (which would break the no-convenio path). These fold into a later code-conditional-formula step. The two singleton direct-base roles were marked `intentional_singleton` to satisfy the semantic-role typo-twin gate. Two red completeness-drift gates in the sweep are pre-existing peer-owned Modelo 303 offenders (`303`/`2009-y-siguientes` and `2023-y-siguientes`); Modelo 210 is confirmed absent from the offender set, so those are not this slice's surface.
