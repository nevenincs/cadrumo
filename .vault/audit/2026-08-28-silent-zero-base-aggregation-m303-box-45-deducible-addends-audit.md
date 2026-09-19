---
tags:
  - '#audit'
  - '#silent-zero-base-aggregation'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:10790c7800fb2c29e509bda926bf85f82422e558ece1f834b5ebfe82893a6f19'
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

### CORPUS-WIDE CONTEXT — box 45 is the only case of its kind

The check was generalised across every modelo whose diseño prints box
identities in its field text. Eighteen do. Both printed conventions were
handled -- `[T] label ([A]+[B])` as Modelo 130 writes it, and
`([A]-[B]). [T]` as Modelo 353 does -- after a target-before-only parser
mis-paired several and produced targets appearing inside their own addend
lists, which is arithmetically impossible and is the reliable tell of an
extraction bug rather than a registry one.

Three patterns exist, and a box-id reachability sweep cannot tell them apart.
The filter that separates them is: does the target have ANY formula, and then
do its leaves genuinely lack the addends' leaves?

1. **Implemented** -- M130, M123, M490, M763, M117, M210, M216, M604, M309,
   M202. Every printed addend reachable. This is the norm, and it is why the
   Modelo 303 departure reads as an oversight rather than an architecture.
2. **Manual at box level** -- M322 and M714. Official boxes *including the
   totals* are `input_kind = manual` and exported; M322 declares only three
   formulas, all semantic. The app computes nothing at box level, so it
   publishes no wrong figure. That is a completeness gap and an operator
   arithmetic risk, NOT under-deduction, and must not be reported as though it
   were. Both nonetheless declare `authority_grade = filing`, which is a
   question for whoever owns that grade's definition.
3. **Computed but short** -- Modelo 303 box 45, alone in the corpus.

Modelo 303 box 27, the devengada total, was checked under the same filter and
is a HAZARD rather than an omission: exactly one leaf reaches the official
addends without reaching box 27, `iva.autorepercutido.intracomunitaria.devengado`,
and the generic casilla carries the same reverse-charge figure into the total.
One redundant representation, not a missing category.

So of eighteen modelos, ten implement their printed identities, two compute no
boxes at all, five dissolved under the filter or the parser correction, and one
computes a total it publishes as authoritative while omitting categories its own
design names.

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
- The generalisation recommendation is DISCHARGED: the corpus-wide sweep above
  ran it, and box 45 is the only harmful case. Re-run it when a modelo gains a
  computed total, not as standing work.
- Settle the generic-versus-explicit intracomunitaria modelling ONCE. The
  explicit `.devengado` and `.deducible` variants are unused by both totals,
  surfacing only in the addend paths of boxes 27 and 45 respectively, while the
  generic casilla feeds both. That is one partially-landed decision, not two box
  tickets.
