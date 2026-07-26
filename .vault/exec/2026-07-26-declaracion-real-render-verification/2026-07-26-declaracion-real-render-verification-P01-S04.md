---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S04'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Verify M190 against its real specimen, covering route R4

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/190`
- `declaracion tests`

## Description

The Modelo 190 profile declares three `named_label` targets against
`min_coverage = "1.0"` with `failure_semantics = "fail_hard"`, which is the
shape route R4 predicts will refuse a whole filing over one legitimately blank
optional box. It was measured through the production extraction path against the
one bundled real specimen.

The prediction does not hold here, and the reason matters. The three targets are
not optional boxes: they are the declaration's own summary totals, printed on the
resumen page as `Numero total de percepciones relacionadas en la declaracion (1)
... 01 1`, `Importe total de las percepciones relacionadas ... 02 1.000,00` and
`Importe total de las retenciones e ingresos a cuenta relacionados ... 03
1.000,00`. A Modelo 190 that reaches the sede necessarily carries all three, so a
floor of 1.0 over exactly these three targets is not over-strict in the way the
route describes. Coverage measured 1.0000 (3 of 3), and the floor was not
changed.

The real headroom problem on this profile is a different one, described under
Outcome: the floor is satisfiable by a fabricated value, so it does not protect
what it appears to protect.

## Outcome

Route R4 is tested and does not reproduce on Modelo 190. Coverage is 1.0000 on
`190/2024-0A` with no missing, malformed or ambiguous targets. The extracted
values are `decl.total-percepciones = 1`, `decl.percepciones-total = 1000.00` and
`decl.retenciones-total = 1000.00`; the two amounts equal the constant the
specimen's own redaction manifest declares was written, and the first is a
perceptor count, which the sanitiser does not rewrite.

The specimen is folded into the shared real-render gate for the coverage floor,
the provenance premise and the manifest-constant check. The existing per-modelo
boundary test already drives it end to end through `parse_declaracion` and
asserts the same three values, so the new gate does not restate that claim; what
it adds is the floor, the premise, and enrolment in the anti-vacuity guard.

The count target is asserted structurally rather than by value: a non-negative
whole `Decimal`. Asserting `1` would pin an accident of which taxpayer's filing
was sanitised, not a property of the form.

Verification: the full declaracion suite passes (`227 passed`).

## Notes

A defect found here cannot be fixed from the files this step owns and is reported
rather than closed. All three targets are `named_label` amount targets, so the
blank-box guard is in scope for them, and on all three it is inert. The guard
compares the captured token against `casilla.number`, and for these casillas that
field carries a fichero-BOE positional range rather than a printed box number:
`136-144`, `145-160` and `161-175`, against printed box numbers 01, 02 and 03.

The consequence is sharper on this profile than on Modelo 390 because of the
floor. Each printed line ends in its box number immediately before the value, so
a blank box leaves `02` as the line's last token, which parses to two euros. That
fabricated value counts as covered, so `min_coverage = 1.0` is satisfied by it
rather than tripped by it. A floor that a fabrication satisfies is protecting
nothing.

The fix means editing casilla TOMLs, which are not extraction-profile TOMLs and
so fall outside this step's grant. It may also belong in the guard's source field
rather than in the data, since `number` appears to serve both the printed-box and
the fichero-BOE positional role; that is a design call recorded for the
coordinator rather than taken here.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy with an empty
degraded-reasons list. No semantic result was relied on.
