---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c8e510c32c6d0032d425df83bcca7fd2cafd3483b7e5ed765f90e8de6dfc9fd6'
step_id: 'S49'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S49

## Outcome

**Refutation confirmed by independent measurement.** `IvaRateKind` is not widened, and the enum is untouched.

## The claim, re-measured rather than accepted

The Step asserts the M390 rate values are effective-dated values of the five existing semantic tiers rather than new tiers, "proven cross-year from the bundled layouts where the 2025 diseño zero-mandates the same casilla numbers the 2024 diseño carries live."

That is a checkable claim about bundled artefacts, so it was checked against the workbooks directly.

## The measurement

Both the 2024 and 2025 M390 diseños carry the same seven rate tokens: `0, 2, 4, 5, 7,5, 10, 21`. `IvaRateKind` declares five members: `GENERAL`, `REDUCED`, `SUPER_REDUCED`, `ZERO`, `EXEMPT`.

The cross-year comparison is the decisive part. The same casilla numbers appear in both years with different mandates:

| casilla | 2024 diseño | 2025 diseño |
|---|---|---|
| `[667]` Tipo 2% — Base imponible | `15 enteros 2 decimales` | `Nota 2` |
| `[668]` Tipo 2% — Cuota | `15 enteros 2 decimales` | `Nota 2` |
| `[669]` Tipo 7,5% — Base imponible | `15 enteros 2 decimales` | `Nota 2` |
| `[670]` Tipo 7,5% — Cuota | `15 enteros 2 decimales` | `Nota 2` |

And `Nota 2` resolves, on five separate sheets of the 2025 workbook, to:

> **Nota 2: estas casillas deben estar rellenas a 0**

So AEAT kept the box numbers and mandated zero into them. That is the signature of a *window that closed*, not of a tier that exists.

## Why this refutes widening the enum

`IvaRateKind` names semantic tiers — the statutory bands a supply falls in. The 2% and 7.5% boxes are the temporary food rates: real values, effective-dated, and demonstrably switched off for 2025 while their casilla numbers persist.

Adding members for them would encode a closed window as a permanent tier, and every consumer that reasons over `IvaRateKind` would carry two bands that no longer exist. The right carrier for an effective-dated value is the rate VALUE axis, which is exactly what `S54` and `S55` landed: `applied_rate` on the observation and `applied_rates` on the selector, both alongside `rate_kind` rather than instead of it.

So the refutation and the accepted design are the same argument seen from two ends: values are dated, tiers are not.

## Scope note

`src/cadrumo/domain/iva/_schema.py` is the Step's scope and is deliberately unchanged. The outcome of this Step is that nothing is edited there, and the reason is now recorded so the same widening is not proposed again from the same fourteen values.
