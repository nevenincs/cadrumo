---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-aitor-cli-testimonial-audit]]"
  - "[[2026-05-27-ramon-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-27 María Reverter Fundación Ley 49/2002 sin fines lucrativos`

## Scope

María Reverter — tesorera Fundación Caritativa San Antonio
(asociación sin fines lucrativos, declarada de utilidad pública,
Ley 49/2002 régimen). 2024: €240k donaciones + €140k venta
productos artesanales + €68k beneficio neto. Two employees.
Exercises Ley 49/2002 régimen, M182 donantes informativa,
DP200014 tipo reducido 10%, Art. 6/Art. 7 rentas exentas
clasificación, M036 alta censal.

## Findings

### CRITICAL — M182 (Ley 49/2002 donantes informativa) entirely absent

`aeat app modelo work create --modelo 182` → "Modelo desconocido
182". Without M182, the entity cannot communicate donante NIFs +
importes to AEAT. Donantes lose IRPF/IS deducción 35-80% via
cruce-de-datos absence. Entity incurs infracción informativa.

€240k of 2024 donations affected for María's case. ~3,200
Ley 49/2002 entities active in Spain.

### CRITICAL — DP200014 tipo reducido 10% Ley 49/2002 NOT applied to cuota

Casilla `DP200014:00558` correctly shows tipo `10`. Casilla
`DP200014:00562` (cuota íntegra) computes €32,200 on €140k base.
That's 23% × €140k — the GENERAL IS tipo. The Ley 49/2002 régimen
specifies 10% (Art. 10 Ley 49/2002 + Art. 29 LIS by remisión):
correct cuota = €14,000.

Overcalculation: €18,200 per Ley 49/2002 entity per €140k of
rentas no exentas.

Same family as Sergio H1 / Aitor G5 (tipo ERD 23% not applied)
but for the régimen-especial branch. Casilla 558 is set as a
display value, NOT consulted by the cuota formula.

### HIGH — Ley 49/2002 opt-in axis absent

Profile has `legal_entity_form = sin_fines_lucrativos` (good —
existed). But no field for:
- Ley 49/2002 opt-in date (M036 opción 105 ejercicio).
- Régimen-especial activation status.

The opt-in is a constitutive act (Art. 14 Ley 49/2002 + DA 16ª
LGT). Without capture, motor cannot verify temporal coherence of
obligations or surface M036 propuesta.

### HIGH — M036 alta/modificacion periods rejected

`aeat app modelo work create --modelo 036 --period alta` returns
"Error. invalid registry period 'alta'". Same for `modificacion`.
M036 exists in catalog (revision `2025-02-03-y-siguientes`) but
the calculator rejects the declared censal periods. M036
declaration unusable.

### HIGH — Art. 6 / Art. 7 LISyD classification guidance absent

DP200014 partition (rentas exentas vs no exentas) is
structurally correct. But CLI offers no guidance on whether the
€140k venta productos artesanales is exempt (Art. 7 explotación
económica vinculada al objeto) or non-exempt. Operator must
decide unguided.

### CONFIRMED — #228 KeyError still bricks `aeat config profile create`

María hit the same `KeyError: 'wizard.setup.flags.situacion-
familiar.help'` blocking second profile creation. #228 still
in-flight via coder2.

### POSITIVE — Several elements work correctly

- `sin_fines_lucrativos` is first-class `--legal-entity-form`.
- DP200014 partition structure is correct (just not wired to
  régimen-conditional cuota).
- M347 works for non-donation operations.
- CIF validation rigorous.

## Recommendations

1. **M182 Path-B refusal stub (CRITICAL)** — add `"182"` to
   `_STUB_ONLY_MODELOS`. Locale citing Ley 49/2002 Art. 18 +
   Orden HAP/2487/2013. Affects ~3,200 entities.

2. **DP200014 tipo 10% formula fix (CRITICAL)** — casilla 562
   formula must read 558 dynamically (not hardcoded 23%). When
   `legal_entity_form = sin_fines_lucrativos`, the régimen-
   especial tipo 10% applies.

3. **Ley 49/2002 opt-in axis (HIGH)** — profile field
   `ley_49_2002_opt_in_date: date | None`. Surface M036 opción
   105 propuesta if absent.

4. **M036 period fix (HIGH)** — register `alta` + `modificacion`
   periods at calculator dispatch.

5. **Art. 6/7 classification guidance (MEDIUM)** — `--exempt-
   activity-art-7` wizard question for `sin_fines_lucrativos`
   entities.
