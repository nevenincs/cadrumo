---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e616a0922b1c93cb33cad7658dcf46e46d6bf631d2405dcff6a8371b6a4d058c'
step_id: 'S19'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Retire the dead advisory cluster on RentaFamilyProfile, opened on a partial measurement naming one property and widened on a fuller one to five members, including the maternidad method superseded by the live free function and the guarderia cap constant whose last Python consumer it is, replacing the cotizaciones-binds-the-cap assertion against the live registry path in the SAME commit

## Scope

- `src/cadrumo/domain/contribuyente/family.py`
- `src/cadrumo/domain/contribuyente/tests/test_incremento_guarderia_0613.py`
- `src/cadrumo/core/external_constants.py`
- `src/cadrumo/core/tests/test_external_constants_centralisation_part2.py`
- `src/cadrumo/locales/`

## Description

The row was opened on a partial measurement and widened on a fuller one before
any code was touched. A code review reported one dead property. Remaking that
measurement, rather than accepting it, found five members: the reported symbol is
dead TRANSITIVELY, not directly, because it has a caller — an advisory wrapper in
the same file that nothing calls. A grep for production callers of the reported
symbol alone stops at that first hop and reports it live.

Executed in this pass:

- Add two live-path assertions that the cotizaciones term and the per-child
  ceiling each bind the cap, before removing the case that asserted the first.
- Retire the guarderia increment method, its advisory, and the pinned-2024 spend
  property.
- Retire the maternidad method and its advisory, superseded by the live free
  function the calculate path calls.
- Retire the guarderia per-child cap constant, whose last Python consumer was the
  first of those.
- Remove two orphaned locale keys from four catalogues through the locales CLI.
- Sweep the constants gate, whose rows asserted imports and guarded literals in a
  file that no longer has either.
- Edit both test modules surgically, keeping the halves that cover the live fact
  boundary and the flag.

## Outcome

Five dead members, one dead constant and two orphaned locale keys are gone, and
nothing that was live went with them.

The maternidad half is the part the original row did not name, and it is the
genuine second authority the Step was opened on the suspicion of. The deduction
existed twice: as a dead method on the profile and as the live free function the
calculate path calls. Deleting only the guarderia half would have left an
identically-shaped dead pair beside freshly deleted code, which reads to the next
person as considered and kept — worse than either deleting or not.

The coverage replacement landed in the same commit as the deletion, which was the
hard precondition. One retired case was load-bearing: the proof that the
cotizaciones term actually binds the cap. Every 0613 value assertion in the tree
was grepped and in none of the survivors did that term win, so deleting first and
replacing after would have left a real term of the cap asserted nowhere while
every gate stayed green. Two cases now pin it against the live registry path
through the real CLI, one where cotizaciones is smallest and one where the
per-child ceiling is, with the ceiling read off the compiled formula rather than
restated so a revision that moves it moves the expectation with it.

Both test modules were edited surgically rather than deleted, which their names
will not suggest to a later reader. Roughly half of each covers the live
persistence boundary and the flag and survives; both module docstrings now record
what was removed and why.

The constants gate was swept in the same change rather than left to rot. Three
rows asserted that the family module imports constants it no longer uses, and two
more guarded against bare literals in a file that no longer computes those
amounts. Those are vacuous guards whose subject this change deleted, and a
vacuous guard is a false green. The equivalent rows for the live maternidad
module are untouched and still bite.

Verification: the full domain, core, wizard, modelo, CLI and locale selection
passes at 7296, with eleven failures that are an exact subset of the set
attributed before this work began and unrelated to it. Lint, type check, the
locale drift gate and the API stub gate are clean.

## Notes

One asymmetry was found and deliberately not fixed, because it is a design
question rather than dead code. Two retired cases asserted maternidad
eligibility, that a child over three or one not cohabiting contributes nothing.
They are not replaced, because the live path has no counterpart to replace them
against: it consumes an operator-supplied list of child and month pairs and
performs no filtering of its own. So the eligibility rule the retired method
enforced existed only in code nothing called, and on the live path an operator
may declare months for a child the statute excludes. That may be the intended
operator-asserted design, since the flag's own name states the condition, but it
is a divergence between the two paths that nobody chose in one place, and it is
worth a decision rather than an inheritance.

The work stopped twice before reaching this point, both times before deleting
anything. First when the dead set proved larger than the row, and again when the
cluster turned out to reach into the core constants and their gate. Both stops
produced a wider and more accurate Step than executing the row as written would
have, which is recorded here because the instinct that produces them is easy to
lose under a clear instruction.
