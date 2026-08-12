---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d1ec681c1d2144672a3528cc7b48522828fc0411abf4ef171313187032f47195'
step_id: 'S322'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Settle the COUNTRY-PREFIX axis of the same-bearer comparison at confirm, the second axis of the over-refusal whose separator axis is already fixed. Measured at HEAD by driving the real confirm path: a document stating the seller identifier in its VAT form and an operator supplying the bare national form are refused as a mismatch, because same_tax_identifier compares on the separator-stripped form and a country prefix is not a separator. Do NOT simply strip a leading alpha-2 from both sides - that would merge bearers across States, since the same national body can exist under two different country prefixes. The comparison must be prefix-aware only where the prefix names the counterparty own country, which means the fix needs the country as an input and cannot be made inside the current two-argument predicate. Treat widening the shared predicate as the risk it is: it is consumed by the identity-role resolver and the document-direction deriver, so a looser rule silently changes who counts as the taxpayer on every document

## Scope

- `src/cadrumo/core`
- `src/cadrumo/application/ledger`

## Description

- Confirm the axis against the shared predicate and establish where the fix can
  safely live.
- Add the country as an input at the confirm call site, discounting only that
  counterparty's own prefix.
- Cover both halves: the over-refusal gone, the cross-State case still refusing.

## Outcome

Delivered. The confirm path no longer refuses two spellings of one bearer.

A document routinely states an identifier in its VAT form while an operator
supplies the bare national form, and the path refused the pair -- telling the
operator to check the tax id printed on the invoice, which is the same dead end
the separator axis produced before it was fixed. Found by driving a real
bundled document through the real confirm path rather than by reading, which is
why it survived a row written from the code.

HANDLED AT THE CALL SITE, NOT IN THE SHARED PREDICATE, and that is the whole
design rather than a placement preference. Stripping a leading alpha-2
unconditionally would merge bearers ACROSS States, because the same national
body can exist under two different prefixes. And the shared same-bearer
predicate is consumed by the identity-role resolver and the document-direction
deriver, where a looser rule would silently change who counts as the taxpayer
on every document read. The confirm site knows the counterparty's country; the
predicate does not, and should not be told.

The helper delegates to the canonical predicate rather than reimplementing it,
so the separator rule keeps one home and this adds exactly one axis on top.

The precision half carries the weight: a German prefix against a counterparty
recorded in Spain still refuses, a genuinely different identifier still
refuses, and the discount follows the counterparty's OWN country rather than a
hardcoded Spain -- a French counterparty stating its prefix against its bare
form is the same situation, and hardcoding Spain would have fixed the domestic
population and left every other one refusing, which is the shape a
Spanish-first codebase produces by default.

## Notes

INCIDENT, DATA LOSS: I DESTROYED EIGHT TESTS AND COMMITTED THE DESTRUCTION.

The new cases were written with a whole-file write to a path I believed was
new. It was not. The existing agreement suite was overwritten and the loss
landed at HEAD before I noticed it, in the commit's own numstat -- eighty-seven
lines deleted from a file I thought had none.

What went with it: the assertion that a refusal names the field and prints
NEITHER value, which keeps a tax identity out of a pasteable artefact; the
case-and-padding parametrisation; the mutation proof that the COMPARISON is
what causes the refusal, without which the suite proves only that a refusal
exists somewhere; and the absence case deferring to the required-field check.

Restored verbatim from the prior commit and merged rather than re-substituted,
so the suite is now fifteen cases. Both destroyed properties are verified
present at HEAD by name. The original call sites were adapted to the widened
signature rather than rewritten, and the country they implicitly assumed is now
a named module constant.

The cause is the one this session kept repeating and this is its worst
instance: writing before reading. Three earlier instances were caught by a
property gate, a module contract and an ADR. This one was caught by nothing --
only by reading my own diff after the fact. A file write is the one edit shape
with no gate behind it, which is exactly why it needs the check the other
shapes get for free.

One docstring paragraph in the restored suite was corrected rather than left:
it recorded that a separator deliberately refuses, on the grounds that the
identity token is trim-and-uppercase only. That was true when written, and the
comparison has since moved to the same-bearer predicate which strips separators
on purpose. The token's rule is unchanged and still right for keying.
