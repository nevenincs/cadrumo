---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-14 Yara Bouhsini Lahjouji single mother baja maternidad refundable deductions`

## Scope

Fourteenth testimonial round, Yara Bouhsini Lahjouji — Madrid
single mother of two children under 3. Took baja maternidad 16
weeks 2024; €16k empleador wages (8 months) + €8k INSS prestación
(exempt under Art. 7.h LIRPF). Two children in escuela infantil
autorizada €350/mo each. Exercises Art. 81 LIRPF maternidad
deduction (refundable €1.200/year/child <3), Art. 81 bis
guardería deduction (refundable €1.000/year/child <3), familia
monoparental reducción €2.150/year (Art. 81 LIRPF). Refundable-
deduction path not previously tested.

## Findings

### CRITICAL — INSS baja maternidad exempt (Art. 7.h LIRPF) not distinguished from empleador wages

The CLI has a single casilla 0003 (Retribuciones dinerarias.
Importe íntegro) for trabajo income. No flag, binding, or
casilla distinguishes:
- **Empleador 8 months: €16.000** — tributable.
- **INSS prestación baja 4 months: €8.000** — EXEMPT (Art. 7.h LIRPF).

A user entering `--casilla "0003=24000"` (total annual cash received)
overpays €2.034,91 in IRPF — the difference between cuota on €24k
and cuota on €16k. No advisory, no warning, no second-pagador axis.

Quantified impact for Yara: devolución €4.290,22 (correct) vs
€2.255,31 (with INSS error) — net loss to the mother is €2.034,91.
Affects every taxpayer who received INSS prestaciones, ANY exempt
income under Art. 7 LIRPF. Silently overstating base imponible.

### CRITICAL — Casilla 0611 deducción maternidad without calculation assistant

Casilla 0611 (deducción maternidad Art. 81 LIRPF, €100/mo/child
under 3 worked) is `input_kind = "manual"` decimal. User must
externally calculate `min(meses_trabajados × 100, 1200) per child`.
No `--meses-trabajo-con-hijo-menor-3` axis, no question prompt.
A user who simply enters €1.200 (single child default) loses €1.200
of refundable deduction for the second child. A user who enters €0
loses €2.400 entirely.

The refundable arithmetic itself works correctly (validated for
Yara's case: 0670 = 0610 − 0611 − 0613 yielded the expected
devolución of €4.290,22). The defect is the input pipeline,
not the engine.

### HIGH — Familia monoparental reducción Art. 81 LIRPF silent loss

Casillas 0209 (Madrid), 0775 (other CCAAs), 0857, 0892, 0938 exist
for monoparental reducción €2.150/year. Profile carries
`--taxpayer-marital-status 1` (soltera) but no `--situacion-familiar
monoparental` axis. The marital-status alone does not imply
monoparental for tax purposes (Art. 82 LIRPF requires unidad
familiar test). The reducción casillas are `manual` with no
profile-binding wire.

A user not knowing the reducción exists loses €2.150 of base
reduction → ~€452 IRPF (Madrid CCAA, low-marginal-rate cohort).

### HIGH — Art. 81 bis guardería cap not validated, cotizaciones SS not cross-checked

Casilla 0613 (incremento por gastos guardería) accepts any decimal.
Legal limit: `min(gastos_reales, €1.000/child, cotizaciones_SS_madre)`.
None of these three constraints is enforced. Casilla 0013
(cotizaciones SS) itself is `manual` not bound from the profile or
M111 previous filing. A user can declare €5.000 in 0613 with
0013 = 0; the CLI accepts and applies the full €5.000 refundable
deduction → AEAT later rejects.

Casilla 0210 (NIF guardería autorizada) is `manual` without binding
to AEAT census of autorizadas centros. NIF mismatch with Modelo 233
(presented by guardería) causes silent post-filing rejection.

### HIGH — `bindings list` (without `--missing`) fails on legal-catalogue validation

`aeat app modelo bindings list --modelo 100 --year 2024 --period 0A`
aborts with `legal catalogue validation failed: legal reference
'rd-439-2007:art-113' corpus text missing required text 'desplazados'`.

`--missing` flag bypasses this. The full bindings discovery path
is blocked for any user trying to understand what their modelo
needs. Same family as #167 / #173 / Sergio H3 / Lourdes F7 — legal-
ref validation overzealous in production paths.

### MEDIUM — Casilla 0065 (situación familiar) disconnected from profile

Casilla 0065 records situación familiar (1 = soltera sin hijos,
2 = casada con hijos, 3 = soltera/separada con hijos a cargo, etc.)
determining mínimo personal y familiar (Art. 57-58 LIRPF). No
binding derives it from the profile's marital-status + descendientes
fields. User must externally know which clave matches their
situation.

### MEDIUM — Casilla 0612 (anticipo Modelo 140) no integration

If the mother claimed anticipated maternidad deduction via Modelo
140 monthly, that amount must be subtracted from 0611. No binding
to historical M140 records; user must remember and enter manually.

### MEDIUM — Refundable deduction amounts have no guidance for calculation

Even though the engine correctly computes 0670 = 0610 − 0611 − 0613,
the user must independently know how to derive 0611 and 0613 amounts.
No CLI verb like `aeat app modelo deduce --maternidad-meses ...` to
auto-compute and inject.

### POLISH — Casilla data-type rejection on NIF input is good UX

`--casilla "0614=X7654321A"` (NIF descendant) was correctly rejected
with: `"La casilla 0614 ('NIF del descendiente') tiene tipo de dato
nif y no acepta valores decimales directos. Usa --binding..."`.
The post-#174 guard works well across non-decimal types beyond
just `text`. Confirms #174 fix scope is broader than just text.

## Recommendations

The CRITICAL INSS-exempt finding is the most operationally important
new finding — every parent on baja maternidad/paternidad in any given
year (~500k Spanish parents annually) is silently overcharged unless
they manually subtract INSS amounts from 0003. Concretely:

1. **INSS exempt path (CRITICAL):** add `--prestacion-inss-exenta`
   axis OR a computed casilla separating empleador rendimiento from
   INSS rendimiento, with auto-application of Art. 7.h exemption.
   Or surface a verification finding when descendientes-menores-3
   are present, sex=F, and trabajo income exceeds historic empleador
   nómina.

2. **Maternidad deduction assistant (CRITICAL):** add CLI verb or
   binding-derived computation for 0611 from `--meses-trabajo-con-
   hijo-menor-3 HIJO=N` per child. Auto-cap at €1.200/child/year.

3. **Familia monoparental axis (HIGH):** add `--situacion-familiar`
   to profile schema. Auto-route to 0209 (Madrid) / 0775 (other
   CCAAs) / 0857 etc. depending on tax-residence CCAA.

4. **Guardería cap + NIF validation (HIGH):** wire 0613 as `computed`
   with `min(gastos_reales, hijos × 1000, cotizaciones_SS_madre)`.
   Validate 0210 NIF against autorizadas registry or warn about
   M233 cross-reference.

5. **`bindings list` legal-catalogue gate (HIGH):** the
   `rd-439-2007:art-113 desplazados` corpus-text validation should
   not abort production paths. Same family as #167/#173 — defer
   non-critical corpus validation to a separate `audit` verb.

The refundable-deduction arithmetic itself is sound. The defect
surface is entirely in the INPUT pipeline: missing axes, missing
profile-to-casilla bindings, missing computation assistants, missing
validations. Pattern-wise: many M100 casillas remain `manual` that
should be `computed` from profile + previous filings.
