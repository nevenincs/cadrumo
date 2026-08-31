---
tags:
  - '#audit'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:885a4e3b9c08d23eebb3d859548b4beaeec49cc05a30fde6ca128e98ec2b169f'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace semantic-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `semantic-consolidation` audit: `negative invoice total liva 89`

## Provenance

Agent-authored from the BUNDLED consolidated corpus. Every quotation below was
read from
`src/cadrumo/_data/corpus/normatives/html/rd-1619-2012.html.extracted.md` and
`ley-37-1992.html.extracted.md`, verbatim. No numeric rate or amount is asserted,
so the live-BOE cross-check that governs numbers is not engaged.

**This is not a reviewed legal ruling.** It is the research the tax review asked
for, prepared so the ruling itself is a short decision rather than an
investigation. It must not be cited as `legal_refs` grounding until a human
reviewer ratifies it.

## The question, restated against the code that exists

`P02.S45` asks whether an invoice total may be negative "before pushing a
non-negative bound onto the canonical invoice". The premise is out of date in
two ways, both worth recording.

The step cites `src/cadrumo/domain/invoices/_models.py`, which no longer exists;
the models are at `domain/invoices/models.py`. And the bound is not prospective.
It is already there:

- `models.py:801` -- `base_total`, `iva_total`, `grand_total` all refuse a
  negative value
- `models.py:526` -- line `unit_price`, `subtotal`, `iva_amount` likewise
- `models.py:520` -- line `quantity` must be strictly positive

So the question is not whether to add a bound. It is whether five bounds already
shipping are correct.

## What the regulation says

**RD 1619/2012 art. 15.5**, on how a rectificativa states its correction:

> los datos que se regulan en los párrafos f) y h) del citado artículo 6.1 se
> podrán consignar, bien indicando directamente el importe de la rectificación,
> **con independencia de su signo**, bien tal y como queden tras la rectificación
> efectuada

Art. 6.1.f) is the base imponible and 6.1.h) the cuota repercutida. The
regulation therefore permits TWO forms, and one of them carries a signed
difference.

**RD 1619/2012 art. 15.2**, second paragraph, on returned goods and packaging:

> se podrá practicar la rectificación en la factura que se expida por dicho
> suministro, restando el importe de las mercancías o de los envases y embalajes
> devueltos del importe de dicha operación posterior ... **con independencia de
> que su resultado sea positivo o negativo**

**LIVA art. 89.Cinco** contemplates the downward direction throughout: "Cuando
la rectificación determine una minoración de las cuotas inicialmente
repercutidas", with art. 89.Uno routing base-imponible modifications through
art. 80.

## Assessment

The two clauses are not the same finding and should not be ruled on together.

**The rectificativa form is a restriction, not necessarily a defect.** Art. 15.5
permits either the signed difference or the post-correction absolute values. A
non-negative model supports the absolute form only. That is narrower than the
regulation allows but it is a form the regulation permits, so an operator can
always comply -- at the cost of being unable to record a rectificativa the way
their counterparty may have issued it.

**The art. 15.2 netting case looks like a genuine gap.** That paragraph produces
an ORDINARY invoice for a later supply, whose result the regulation explicitly
allows to be negative. There is no absolute form to fall back on: the document
is what it is, and its total is below zero. A non-negative `grand_total` cannot
represent it.

## What is needed, and what was deliberately not done

The bounds were NOT removed. Widening what the invoice model accepts changes
what the application will carry into a filing, on a regulated surface, and the
`no-silent-under-declaration` companion cuts both ways here -- a negative total
admitted carelessly is as much an error as one refused wrongly.

The ruling needed is narrow:

1. Does the product intend to support the signed-difference rectificativa form,
   or require the absolute form (art. 15.5 permits either)?
2. Is the art. 15.2 netted-return invoice in scope? If yes, `grand_total` at
   minimum must admit a negative value, and the arithmetic validator and every
   downstream aggregation need re-examining for the same assumption.

Question 2 is the one that decides whether this is a restriction or a defect.
