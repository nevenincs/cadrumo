---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a0656bc9283fc71ae791c12c0f74d868abec0ce135a188d025396172ee86bd4f'
step_id: 'S15'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Give the Art. 81.1 maternidad adoption clause its own date-scoped three-year window, separate from the Art. 58.2 period-scoped one, BLOCKED on S21 because nothing on the calculate path reads a descendant record for maternidad, so the predicate would land with no consumer and rebuild the dead shape S19 removed

## Scope

- `src/cadrumo/domain/contribuyente/family.py`

## Description

Add `art_81_1_entry_window_meses`, counting the months of a period inside the
three-year window measured from the entry event's DATE rather than from its period.

Extract a shared half-open month-span helper, so both Art. 81.1 limbs count their
opening month in full and exclude the month the span runs out.

Union the entry-window months with the under-three months in the eligible window the
deducción caps against, giving the predicate a production consumer.

Anchor the window on the first entitling event, so a fostered-then-adopted child draws
one window rather than two.

Prove the divergence from the Art. 58.2 period window in both directions, and drive the
limb end to end through the real CLI.

## Outcome

The Art. 81.1 adopción clause is now its own predicate rather than borrowing the
Art. 58.2 one. The two disagree for the same child in both directions, which is what
distinguishes two windows from one: a child inscribed in November 2021 is granted the
whole 2021 period by Art. 58.2 while only its last two months fall inside the date
window, and 2024 is ten months inside the date window after Art. 58.2 has closed.

The consumer clause is satisfied rather than asserted. A five-year-old adoptee yields
1.000 at the maternidad casilla for 2024 through the real CLI, and every month of it
came from the entry window because the under-three limb grants that child nothing.

The limbs union rather than one shadowing the other. An infant adopted in October is
under three all year and inside the entry window from October; neither limb's own count
is twelve and the answer is.

## Notes

The entitling relación set is shared with Art. 58.2, and that was checked rather than
assumed. The two statutes enumerate differently on their face — one names acogimiento
"tanto preadoptivo como permanente", the other "acogimiento permanente o delegación de
guarda para la convivencia" — which reads as a narrower set for the deducción. It is
not: the delegación de guarda is the successor figure to the abolished acogimiento
preadoptivo, so the enumerations cover the same placements under different vocabularies.
Recorded at the predicate, because a reader comparing the two phrasings will otherwise
re-open it and may narrow the set into an under-grant.

The month span compares year-month pairs rather than constructing an anniversary date.
That is load-bearing for a 29 February event, whose anniversary does not exist in a
non-leap year and raises on construction.

The sequential suite was red at 60 failures and 19 collection errors across Modelo 210,
202, 303, 349, 131 and 100 during this Step's verification window, while a peer campaign
rewrote several thousand registry casilla TOMLs in the working tree. Every implicated
module was re-run afterwards and passed, so the run had read a half-rewritten registry
rather than a regression. No failing module was one this Step touches.

The Art. 81.1 window is now modelled but the operator's declared months remain a single
annual count per descendant, so a taxpayer whose entitlement spans a window boundary
still declares one figure that the engine can only cap. That is sufficient for the
windows implemented here and is the same shape the post-alta increment will have to
change.
