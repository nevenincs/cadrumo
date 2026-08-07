---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ce502049eb4071062311c994fb2d2aeea662524ee93aac2c3afa3c25153f3213'
step_id: 'S56'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S56

## Outcome

**Unblocked, and by correcting this record rather than by anything changing.** The blocker the earlier pass recorded was wrong, and the evidence refuting it was already in `W06.P08.S49`'s own measurement — I had it in hand and read it backwards. The crossing needs no revision split and no schema change. What remains is bounded work that belongs to the M390 under-modelling campaign `S47` scoped.

## The blocker, and why it was wrong

The earlier pass concluded that adding per-rate casillas for the temporary 2 %, 5 % and 7,5 % rates would "model, for the current filing year, boxes AEAT has switched off", because `CasillaDefinition` carries no validity dates and M390 has one revision open from 2010.

AEAT did not switch off the boxes. `S49` measured exactly what it did:

| casilla | 2024 diseño | 2025 diseño |
|---|---|---|
| `[667]` Tipo 2 % — Base | `15 enteros 2 decimales` | `Nota 2` |
| `[668]` Tipo 2 % — Cuota | `15 enteros 2 decimales` | `Nota 2` |
| `[669]` Tipo 7,5 % — Base | `15 enteros 2 decimales` | `Nota 2` |
| `[670]` Tipo 7,5 % — Cuota | `15 enteros 2 decimales` | `Nota 2` |

with `Nota 2` reading *estas casillas deben estar rellenas a 0*.

The boxes are on the 2025 form. AEAT kept the numbers and mandated a zero into them. So a casilla present in every filing year **is** the correct model of the form, and the zero mandate is satisfied rather than violated: no 2025 transaction can carry a 2 % applied rate, because the rate table's effective dates make that impossible, so the binding resolves zero on its own.

The date-shape that seemed missing is already there, one layer down. `S53`, `S54` and `S55` landed it — `applied_rate` on the observation and `applied_rates` on the selector, effective-dated at the VALUE axis. `S49`'s closing line says it outright: *values are dated, tiers are not*. A casilla that exists always and resolves zero when no dated value reaches it is that design working, not a gap in it.

## The revision-shape question was also mis-framed

The earlier pass offered two shapes and called them both defensible: split M390 by year "as AEAT versions its diseño", or effective-date casillas. Measuring the registry instead of reasoning about it gives a different picture.

Sixty-four of seventy-three modelos carry ONE open-ended `-y-siguientes` revision. Nine carry more, and only two of those nine split every year — M100 and M131, whose scales and módulos change annually. The rest split where the LAW changed: M303 at `2009` → `2023`, M180 at `2019-2022` → `2023`, M202 across three windows, M123 at `2019-2023` → `2024`. M369 does not split temporally at all; it splits by esquema.

So a revision boundary marks a legal change, not a calendar year, and M390's single revision is the convention rather than the anomaly. Splitting it by year would have been the deviation. Effective-dating `CasillaDefinition` would have been worse — a second time axis for a fact the revision window and the rate values already carry between them, which is a duplicate authority by construction.

Neither shape was needed. That is the part worth keeping: two options both argued as defensible, and the right answer was that the question did not arise.

## What actually remains

Adding casillas `[667]`–`[670]` with their rate-selecting bindings, grounded in the 2024 diseño. That is real work and it is not this Step's, for the reason `S47` recorded when it scoped the annual under-modelling: M390 is modelled at 22 casillas against 375 official boxes, and any new annual casilla bound to ledger IVA joins the reconciliation parity gate and must match its quarterly counterpart's category set. Adding four boxes without their M303 counterparts reds that gate.

So it enrolls under the scoped campaign with its dependency stated, rather than being smuggled in here as four casillas that happen to fit.

## Scope note

`src/cadrumo/_data/registry/aeat/modelos/390/` is unchanged, as before — but now because the work is sequenced elsewhere, not because it is inexpressible.

## The campaign this routes to does not exist yet

The disposition above sends the four casillas and their bindings to the M390
under-modelling campaign that `W06.P08.S47` scoped. No such plan has been opened.

The routing is still correct -- the work genuinely belongs with the rest of the
annual surface, and adding four boxes here without their Modelo 303 counterparts
would red the reconciliation parity gate. But "enrolls under the scoped campaign"
should not be read as "scheduled". The close honesty review carries this as
`FINDING-3`.
