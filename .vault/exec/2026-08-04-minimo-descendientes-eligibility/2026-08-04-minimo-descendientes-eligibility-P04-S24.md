---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b9aa2f6e5de3fa002b42ff1df850979e36ef8ca3384a133b33bd2189fbf68869'
step_id: 'S24'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Collapse the two family-record reconstructions in _profile_binding onto their UNION rather than onto either one, because each carries what the other lacks, the guarderia path pre-checks every birth date and raises naming the row index while omitting the anualidades that suppress dependency assimilation, and the minimo and maternidad path carries the anualidades while having no pre-check, so collapsing onto the minimo variant silently loses the indexed diagnostic and collapsing onto the other silently over-grants for a filer paying judicial anualidades, and adding anualidades to the guarderia injector must be recorded as a stated no-op since the guarderia count does not read them

## Scope

- `src/cadrumo/application/modelo/_profile_binding.py`
- `src/cadrumo/domain/contribuyente/family.py`

## Description

Collapse the two family reconstructions onto one carrying the UNION of what each had:
the indexed birth-date pre-check and the filer's declared anualidades.

Delete the redundant second reconstruction and route its two call sites to the union.

Route the calculate-path resolver's maternidad pairing to the domain method that
already computed it, rather than recomposing it inline.

Make the withheld and alta-posterior lookups explicit about the sparse mapping the
pairing returns.

## Outcome

One reconstruction, so a malformed stored birth date now names its row on every path
and the anualidades carve-out applies to every eligibility question rather than to
whichever path the caller happened to take. Neither property was safe to drop: without
the pre-check an operator is told a date is bad but not which descendant carries it,
and without the anualidades an eligibility question answers with the dependency
assimilation always available, over-granting for a filer who pays judicial anualidades.

The guarderia injector used the pre-check variant and therefore gains the anualidades.
That is a no-op by inspection rather than by accident -- the count it feeds does not
read them -- and it is stated at the function so a later reader does not take it for a
behaviour change.

The pairing now has exactly one home and one production consumer. Verified through the
real resolver over a three-descendant record mixing an eligible child, an over-three
child and a temporal acogimiento: pairs carry only the eligible index and the withheld
set names the other two, including across the sparse-mapping boundary the delegation
introduced. 384 domain and application tests pass, 29 CLI integration tests pass.

## Notes

Both halves of this Step were the same question -- dead, or a second authority -- and
both resolved as second authority rather than dead. The pairing method was correct and
tested; what was missing was its consumer, so the fix was to route production through
it rather than to delete it. Deleting a correct domain method because production had
drifted around it would have removed the better of the two implementations.

A scripted removal of the redundant reconstruction was guarded by an assertion on the
span it would cut, and the guard fired: the naive span reached past the function into a
dataclass that had to survive. The bound was not widened; the span was made precise.
That guard cost one line and prevented a silent deletion no test would have named.

Landed through commit-tree with a diff-tree guard after a pathspec commit failed on
index-lock contention and HEAD moved underneath it. The guard confirmed the written
tree touched exactly the two intended paths before the ref moved.
