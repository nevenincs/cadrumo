---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:96ba451e4ae1b163ceac769c1413c7429f67b8b3f57865ea70711967d0bf6b27'
related: []
---

# `semantic-consolidation` audit: `zero base imponible`

## Provenance

Agent-authored from the BUNDLED consolidated corpus
(`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md`),
quoted verbatim. No rate or amount is asserted. **Not a reviewed legal ruling**
-- it is the research `P08.S39` asks for, and must not be cited as `legal_refs`
grounding until a human reviewer ratifies it.

## The four sites

`P08.S39` describes "two sites forbid and two allow". They are:

**Forbid zero:**

- `domain/contribuyente/assets/records.py:141` --
  `taxable_base: Decimal | None = Field(default=None, gt=Decimal("0"))`
- `domain/renta/_ledger_expenses.py:179` --
  `gross_amount: Decimal = Field(gt=Decimal("0"))`

**Allow zero:**

- `domain/transactions/model_validation.py:41` -- non-negative, with a stated
  reason: the base is IVA-exclusive and direction comes from the transaction,
  not the sign
- `domain/contribuyente/inventory/records.py:171` -- cents normalisation only,
  no sign or floor bound

## Is a zero base imponible legitimate?

Yes, and by two independent routes.

**LIVA art. 80.Uno.2** reduces the base by "Los descuentos y bonificaciones
otorgados con posterioridad al momento en que la operación se haya realizado
siempre que sean debidamente justificados." A full bonificación reduces it to
zero.

**LIVA art. 80.Dos** is the stronger one:

> Cuando por resolución firme, judicial o administrativa o con arreglo a Derecho
> o a los usos de comercio **queden sin efecto total** o parcialmente las
> operaciones gravadas o se altere el precio después del momento en que la
> operación se haya efectuado, la base imponible se modificará en la cuantía
> correspondiente.

An operation annulled in full has its base modified to zero. The statute
contemplates the state directly.

## The assets model contradicts itself

Independent of the legal question, `assets/records.py` is internally
inconsistent at lines 141-146:

- `taxable_base` is `gt=Decimal("0")` -- zero refused
- `iva_amount` is `ge=Decimal("0")` -- zero accepted

and the model's own arithmetic validator (line 166) asserts
`iva_amount == taxable_base * iva_rate`. A zero base with zero IVA satisfies
that arithmetic exactly, and is refused only by the base's floor. The two
bounds on the same record disagree about whether zero is a real state.

That is a defect regardless of how the tax question is ruled, and it is the part
that does not need a tax reviewer.

## Assessment, per site

`gross_amount` on a renta deductible-expense line is the weakest candidate for
change: a zero-amount deductible expense carries no deduction and asserts a line
that does nothing. `gt=0` there is defensible on meaning rather than on statute.

`taxable_base` on a bien de inversión is the real question. A fully-annulled
acquisition would not be an asset record at all, but a fully-discounted one
plausibly is, and the model already tolerates the zero-IVA half of that state.

## What is needed

The bounds were NOT changed. This is a regulated surface feeding renta
deductible expenses and bien-de-inversión regularisation, and
`no-silent-under-declaration` cuts both ways: a zero base admitted carelessly
under-declares as surely as one wrongly refused blocks a legitimate filing.

The ruling needed:

1. Should `assets.taxable_base` admit zero, matching `iva_amount` on the same
   record and art. 80? The internal contradiction should be resolved either way.
2. Is `gross_amount > 0` on a renta expense line intended as a meaning
   constraint rather than a tax one? If so it should say that, because it
   currently reads as the same bound and invites exactly this collapse.

Question 2 matters for the campaign specifically: the step's premise was to
COLLAPSE these four onto one canonical bound. If two of them are the same rule
and two are different rules that merely look alike, collapsing them would create
the shared-name-different-meaning defect this campaign exists to remove.
