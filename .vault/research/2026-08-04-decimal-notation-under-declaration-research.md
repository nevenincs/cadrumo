---
tags:
  - '#research'
  - '#decimal-notation-under-declaration'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:84713854ab8aefced7cadb5561699341c8429e17e4e88cf9bca67a9fd3667155'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-adr]]"
  - "[[2026-08-04-minimo-descendientes-eligibility-audit]]"
  - "[[2026-07-30-open-work-consolidation-plan]]"
---

# `decimal-notation-under-declaration` research: Spanish thousands separator silently misread as a decimal point

## Context

A live, silent under-declaration measured on 2026-08-04 on the documented operator entry
surface. Recorded before any remedy is designed, because the defect currently exists only
in session messages and an acknowledged defect that lives only in a dispatch does not
exist.

Found while chasing an unrelated and much smaller question — whether the guided flow
accepts a cents figure. The path to it is worth recording: the guided flow was measured to
refuse cents loudly, which was the good outcome; the executor then observed that the
comma-decimal form is refused on *both* surfaces and flagged that as a Spanish-locale gap
worth stating independently of the cents question. Probing one form further along that same
axis found the defect. Neither the cents question nor the comma observation was itself the
problem.

## The measurement

The operator-facing descendiente flag parses a rentas figure through the shared canonical
decimal parser. Measured behaviour across the four forms a Spanish taxpayer might type:

- `8000` — accepted, eight thousand. Correct.
- `8000.50` — accepted, eight thousand and fifty cents. Correct under dot-decimal reading.
- `8000,50` — refused. Loud, no misread.
- `8.000,50` — refused. Loud, no misread.
- **`8.000` — ACCEPTED, and parsed as eight euros.**

The last is the defect. In Spanish notation the dot is a thousands separator, so a taxpayer
entering eight thousand euros records eight — a factor-of-one-thousand misread with no
refusal, no advisory, and nothing in the stored value that looks wrong.

## The tax outcome

Driven through the production injector rather than reasoned. A descendant earning 12.500
euros is above the Art. 58.1 ceiling and must be excluded from the mínimo:

- typed `12.500` in Spanish notation — stored as 12,50 — mínimo **2.400 granted**
- typed `12500` — stored as 12.500 — mínimo **0**, correct

The misread lands on the claiming side of a strict `>` comparison, so it grants a mínimo
that reduces the base. That is an under-declaration of the tax, silent, on the notation a
taxpayer reads off their own document, in an application whose entire domain is Spanish.

Note the boundary case that masks it in casual testing: at exactly `8.000` versus `8000`
both readings produce the same mínimo, because the ceiling excludes only figures strictly
above it and 8.000 is not above 8.000. A probe using the threshold figure itself shows no
divergence. The defect only becomes visible with a figure that should exclude.

## What is not yet known

The blast radius is being measured and is the open question. The ambiguity lives in the
shared canonical decimal parser rather than in the descendiente flag, so every
operator-facing money input that reaches it is in scope — ledger amounts, guardería spend,
cotizaciones, invoice figures, any `--amount`. A silent thousand-fold misread on a ledger
amount would be materially worse than on a rentas figure, because it feeds aggregation
rather than a single threshold test.

A coordination hazard applies: a peer campaign is mid-refactor consolidating decimal
parsing onto the canonical helpers, which is exactly the code that owns this. The remedy
may belong inside that work rather than beside it.

## The decision this needs

The remedy is a product decision as much as a technical one, and it should be made
explicitly rather than settled by whoever writes the patch first.

Refusing every ambiguous form is the safe direction, but a rule such as "refuse a dot
followed by exactly three digits" also refuses a legitimate `8.000` meaning eight euros
exactly. Accepting Spanish notation properly is friendlier to the taxpayer and carries its
own ambiguity in the other direction. A third option is to require an unambiguous form and
say so at the boundary.

The constraint that is not negotiable: **no input may be silently misread by three orders
of magnitude.** A loud refusal naming both accepted forms is an acceptable outcome. A
silent misread is not, and is barred by the no-silent-under-declaration discipline.

Worth grounding before deciding: whether this project has already made a canonical
Spanish-notation decision somewhere. It is a Spanish-stem codebase and the question is
older than this defect.

## Companion findings from the same surface, both bounded

Recorded here because they were measured in the same pass and would otherwise be
re-derived.

The guided flow's rentas page is integer-only and refuses a cents figure loudly, honouring
the rejection rather than advancing. The operator is blocked and told. The residual concern
is that the only workaround — rounding to whole euros — crosses the same strict `>` in the
under-declaring direction, and the refusal message names the wrong constraint: it reports
an invalid integer rather than saying the field takes whole euros. The sibling gastos page
is integer-only too, so this is a consistent design rather than an oversight, and that one
feeds a proportional deduction rather than a threshold test, so rounding there loses cents
without flipping an outcome.
