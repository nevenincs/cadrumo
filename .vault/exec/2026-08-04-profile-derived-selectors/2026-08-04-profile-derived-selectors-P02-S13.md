---
tags:
  - '#exec'
  - '#profile-derived-selectors'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:6a7e7ff3d6c255dfef76ccd49bd18ad0b539f76c4956f522ca6eeaae0efff7aa'
step_id: 'S13'
related:
  - "[[2026-08-04-profile-derived-selectors-plan]]"
---

# Retire the write-time emission of the guarderia aggregate from the descendant projection AND add its calculate-time injection in the same commit as the refusal, injecting UNCONDITIONALLY with a zero default exactly as its menores-3 sibling does, never preserving the current emit-only-when-positive shape, because a conditional emission is the one derived pattern that legitimately resolves to nothing on an ordinary filer with descendants and no childcare spend and would therefore false-fire the later advisory on the majority case, and because that aggregate is otherwise the only one of the four with no injector so a childless or zero-expense filer leaves its casilla unresolved today

## Scope

- `src/cadrumo/domain/contribuyente/_descendant_facts.py`
- `src/cadrumo/application/wizard/_checkpoint_store.py`
- `src/cadrumo/application/modelo/_profile_binding.py`

## Description

## Outcome

The guarderia aggregate moved from write-time materialisation to calculate-time injection, in
the same commit as the refusal, and the shape it took closes two problems rather than one.

The same-commit requirement was not stylistic. The descendant projection emitted that
aggregate into the same batch as the per-child facts, and the validator judges a whole batch,
so a refusal landing while the emission stood would have refused every legitimate childcare
save -- the precise surface the refusal message directs the operator to, for the precise
scenario the aggregate exists to compute. A grounding pass found this before an executor
reached the Step; the plan originally placed the retirement a whole phase later.

Retiring the emission alone would have been equally unsafe, because a formula-consumed casilla
depends on the value. Both halves therefore rode together.

The injection is UNCONDITIONAL with a zero default, mirroring its menores-3 sibling rather
than preserving the emit-only-when-positive shape it replaced. That shape mattered: it was the
one derived pattern that legitimately resolved to nothing on an ordinary filer with
descendants and no childcare spend, so carrying it forward would have made the later
derived-scoped advisory false-fire on the majority case -- the failure the ADR's own rationale
warns against, where an advisory that cries wolf is worse than none.

Making it unconditional also retired a latent defect nobody had set out to fix: because the
old emission only fired on a positive sum, a childless or zero-spend filer left the binding
unresolved and its casilla with it, rather than a legally correct zero.

Proved three ways at the injector: childless yields zero, an under-three with no spend yields
zero, an under-three with spend yields the real sum. The regression this phase was most likely
to cause was tested directly rather than reasoned about -- a legitimate childcare save emits
only per-descendant facts and the count, so nothing is refused.

## Notes
