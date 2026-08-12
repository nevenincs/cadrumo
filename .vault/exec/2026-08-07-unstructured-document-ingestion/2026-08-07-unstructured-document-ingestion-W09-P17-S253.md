---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:43325227013768b4949664132c086a3638a285d9ca3f0612d40564fe71a80675'
step_id: 'S253'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Judge the nine remaining default-to-Spain sites, in THREE syntaxes rather than the two the earlier census assumed. Thirteen exist in production. Four are registry bindings, two detail-record, one donativo and one withholding, which an earlier census judged plausibly correct by construction since those selectors are Spain-scoped, and that reasoning needs re-testing per site rather than inheriting. Four sit in the row-set assembly as _coerce_text with an ES default AND an or-ES fallback, DOUBLE-DEFAULTED, so removing the visible half leaves the behaviour unchanged and a lane fixing it would believe it had fixed the site. Five are in bulk import, the wizard and the identity roles. The third syntax is the bare annotation default, which is neither Field(default=...) nor an or-expression and hides from a search for either. The question per site is not only whether the default is wrong but what the site does with a case it was not built from, since Spanish is the shape these instruments were built from and every other case is invisible to them rather than reported. Coordinate ownership before editing, since the row-set assembly sites may belong to an active lane

## Scope

- `src/cadrumo`

## Description

- Census the sites in all three syntaxes, separating a DEFAULT from a named
  constant used for comparison.
- Read what each site does with a case it was not built from.
- Judge each, and route the ones whose answer is a tax question rather than a
  code question.

## Outcome

JUDGED. The census is EIGHT defaulting sites, not nine or thirteen, and the
difference is the third syntax: several matches for a bare ``"ES"`` are named
constants COMPARED against, not defaults. Those are correct usage and are not
this row's population, which is worth stating because a sweep keyed on the
literal would have "fixed" them.

THE TWO ROW-SET ASSEMBLY SITES, and the row's warning about them is exact. Both
read ``_coerce_text(fields.get("country_code"), default="ES") or "ES"``, and the
helper returns its default for ``None`` and the value itself for an empty
string -- so the visible default catches an absent field and the trailing ``or``
catches a blank one. Removing either half alone changes NOTHING, and a lane
fixing the one it saw would have every reason to believe the site was closed.

Their declarable populations are the same question S255 raises, and the answer
is not a code reading. One feeds a per-perceptor withholding observation, and
the withholding forms include the non-resident population -- where a perceptor
is foreign BY CONSTRUCTION. The other feeds an attribution member observation,
and an attribution member can be a non-resident, which is exactly what a
sibling row's participe clave exists to state. In both the field is a plain
string, so ABSENCE IS UNREPRESENTABLE and the default converts an unknown into
a positive assertion with no third state.

THE THREE REGISTRY BINDING SITES are S255's, already routed to a tax review and
not re-judged here.

THE THREE REMAINING are a different class and are judged SOUND as they stand.
The invoice wizard's fallback, the identity-role resolver's final fallback after
it has tried the printed identifier, and the confirm path's documented
counterparty-country default are all operator-facing: the operator is present,
can override, and the default is visible in the surface they are using. That is
not the silent-data-default shape -- it is a form pre-fill.

## Notes

COORDINATION, which the row made a precondition. The row-set assembly file has
two recent commits from a types-and-style lane rather than a behaviour lane, so
no active owner is editing its semantics; the sites are free to change once the
declarable-population question is answered. They are NOT changed here, because
the answer is a tax review and this row's deliverable was the judgement.

The finding worth carrying past this row: the double default is not a tidiness
problem but a MEASUREMENT problem. Any future census that greps one syntax will
report these two sites as clean after a partial fix, and the site will still
default. Whoever closes them should remove both halves in one change and prove
absence reaches the model, rather than proving the literal is gone.
