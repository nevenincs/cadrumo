---
tags:
  - '#audit'
  - '#silent-zero-base-aggregation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:1cedf3d060e8de67892e1ef1c3d90cf5a6ad4116e153cb9b9726fade0979503a'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-audit]]"
---

# `silent-zero-base-aggregation` audit: `Modelo 303 box 45 omits five official deducible addends`

## Scope

Modelo 303's `Total a deducir` box and the ten addends the official diseño de
registro names for it, across all six loaded revisions (2022, 2023, both halves
of the split 2024, 2025, 2026-y-siguientes). Registry data only; no engine run
and no profile substrate. Reached by extending the recargo tier-enumeration
check from the devengada side to the deducible side, which is the direction
`no-silent-under-declaration` records as unwatched.

## Findings

### CONFIRMED — box 45 omits five official addends, and the taxpayer overpays

The bundled diseño states the identity in its own field text, in both the
2022-y-siguientes and 2026-y-siguientes workbooks:

`Liquidación (3) - Regimen General - IVA Deducible - Total a deducir ( [29] +
[31] + [33] + [35] + [37] + [39] + [41] + [42] + [43] + [44] ) - Cuota [45]`

and, separately, `Resultado régimen general ( [27] - [45] )`, so box 45 feeds
the amount payable directly.

Box 45's only formula argument is `iva.cuota-deducible-total`. There is exactly
one formula per target in this revision, so nothing is hidden behind a second
fragment. That total's complete TRANSITIVE leaf set is six items: `43`, `44`,
`iva.autorepercutido.interior.deducible`, `iva.autorepercutido.intracomunitaria`,
`iva.soportado.importaciones`, `iva.soportado.interiores`.

Comparing leaf SETS rather than box ids is what isolates the real gap, because
three official boxes do arrive under semantic aliases -- `[29]` as
`soportado.interiores`, `[33]` as `soportado.importaciones`, `[37]` as the
intracomunitaria cuota. Five contribute nothing at all:

- `[31]` cuotas soportadas en operaciones interiores con **bienes de inversión**
- `[35]` importaciones de **bienes de inversión**
- `[39]` adquisiciones intracomunitarias de **bienes de inversión**
- `[41]` **rectificación de deducciones**
- `[42]` **compensaciones Régimen Especial A.G. y P.**

Each is a deducible cuota, each is `input_kind = manual`, and each carries
export refs. An operator can type a capital-goods deduction into `[31]`, watch
it render into the fichero, and box 45 will ignore it. The filed return is then
internally inconsistent against an identity the form itself prints, and because
the resultado is `[27] - [45]`, the taxpayer is told to pay MORE than owed.
There is no refusal, no advisory and no gate: the output is well-formed and
wrong in the taxpayer's disfavour.

### The asymmetry that rules out a deliberate design

`[43]` and `[44]` are also `manual` and exported -- the identical kind -- and
they DO reach box 45; they are the only two addends arriving by box id rather
than by semantic alias. Of seven manual deducible boxes, two are wired into the
total and five are not. Were the architecture "box 45 derives from the semantic
layer and never from box ids", 43 and 44 would not be there either. The wiring
pattern exists, is used, and was applied to two of seven.

### Not novel as a CLASS, and not previously recorded for this modelo

`2026-06-19-silent-zero-base-aggregation-audit` records the same shape for a
DIFFERENT modelo: M390's `cuota-deducible-total` omits the import deducible and
"over-states the amount to pay for an importer", and it rules the fix ADR-scale
rather than a bounded mirror. No equivalent record was found for M303 box 45.

## Recommendations

- Do NOT patch `iva.cuota-deducible-total` by appending five operands. Bienes de
  inversión is an active workstream (the cross-period prorrata audit cites a
  bienes-inversión unblock and a casilla-43 automatic feed), so `[31]`, `[35]`
  and `[39]` may be intended to arrive through a resolver rather than as manual
  operands. A one-line fix would pre-empt that design.
- Fold into the calculation-aggregation taxonomy ADR amendment the sibling audit
  already recommends, alongside the M390 import-deducible finding.
- `[41]` rectificación de deducciones and `[42]` compensaciones A.G. y P. have no
  visible owner in the bienes-inversión thread and need one named explicitly.
- Add a parity assertion that box 45 equals the sum of its ten official
  addends. It is grounded on the diseño's own text, and validates the whole
  dual-derivation rather than one box.
- Generalise the check: this was found by asking whether a total enumerates its
  officially declared addends. Run the same question against every modelo whose
  design states a formula in its field text.
