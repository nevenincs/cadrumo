---
tags:
  - '#adr'
  - '#minimo-descendientes-eligibility'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e17259f73457b2470c33aff2f62d239a5105b85eb6f8326ababa11915f728042'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-deferred-descendant-axes-adr]]"
  - '[[2026-08-04-minimo-descendientes-eligibility-research]]'
---
# `minimo-descendientes-eligibility` adr: `The cotizaciones ceiling is a household term against a per-child limit` | (**status:** `accepted`)

## Problem Statement

Art. 81 bounds the guardería increment TWICE in the período impositivo in which a child
turns three. It bounds the gastos window — spend counts only up to the month before the
second cycle of educación infantil may begin — and it bounds the cotizaciones limit by
the same month: "las cotizaciones a la Seguridad Social a computar serán las devengadas
hasta el mes anterior a aquel en el que el hijo pueda iniciar el segundo ciclo".

The window limb now reads an operator-declared month. The cotizaciones limb does not.
This record states why it does not, and what would have to be settled before it could.

The stakes are direction. Leaving the cotizaciones limb unbounded OVER-grants, which
under-declares tax, in exactly the population the window limb was corrected for. Closing
the visible half while leaving that unsaid would have replaced a measured defect with an
unmeasured one.

## Considerations

- The ceiling is normative rather than a parenthetical: it carries its own heading in all
  six bundled renta manuals, 2020 through 2025, as "Especialidad: aplicación del
  incremento hasta que el hijo comience el segundo ciclo de educación infantil".
- AEAT declines to fix the month. Every statement in every year is subjunctive — "aquel
  en el que PUEDA comenzar", "PUEDA iniciar" — because when the cycle may begin depends
  on the child's región and centre rather than on the calendar.
- No worked example anywhere binds the ceiling, and this is a searched absence rather
  than an assumed one. Each year carries one Ejemplo; in every one the ceiling sits above
  every qualifying month, or the child never turns three so no window exists.
- The corpus states no rule for apportioning one household cotizaciones figure across
  several children whose ceilings fall in different months.
- The stored figure is an annual scalar. No month axis exists on it anywhere in the
  profile model, the fact round-trip, the wizard, or the CLI surface.
- The registry formula applies it as a household-level minimum against the summed
  per-child increment, so one scalar faces as many ceilings as there are children.
- A prior author met this same boundary and declined to cross it, recording in the
  formula that the cotizaciones term "stays a term ... under its own review; folding it
  into the resolved value would decide that question here by accident".

## Considered options

**A. Disclose the bound and do not compute it.** CHOSEN. The engine applies the declared
figure as supplied, and where an unbounded ceiling can change an outcome it tells the
operator the figure must be the one devengada up to the month before the second cycle may
begin. Nothing is invented; the gap is visible and the operator can act on it.

**B. Give the cotizaciones figure a month axis, then bound it.** Rejected as
INSUFFICIENT, not as expensive. It is the same class of migration as the mother's
worked-months change from a count to a month set, and it closes the first obstacle — but
a household figure carrying months still cannot serve two children whose ceilings fall in
different months. It buys nothing alone while looking exactly like a fix.

**C. Collect the cotizaciones figure per child.** Not rejected; out of scope here. It is
the only option that avoids inventing arithmetic, because the operator supplies the
attribution rather than the engine deriving it. It presupposes the ceiling is per child
in law, which this record does not settle.

**D. Compute an apportionment.** Rejected. Any rule — pro rata by month, by child, by
qualifying spend — would be this project's invention wearing regulatory clothing. This
box has already shipped one confidently-applied month rule that was wrong, and that
defect is why this line of work exists.

## Constraints

The blocking constraint is AUTHORITY, not engineering. The apportionment is unstated and
the ceiling's own month is one the authority explicitly declines to fix. No amount of
shape work removes a rule that has not been written.

A second, subordinate constraint: the current household-level application of the
cotizaciones term may itself be wrong. The manual's sentence is written per child. If the
household application is the error, this record UNDERSTATES the problem and the correction
is larger than the apportionment question. That is the first thing a successor record must
settle, and it is deliberately not settled here — asserting it either way would be the
same fabrication this record refuses elsewhere.

## Implementation

What shipped is option A. The gastos window reads an operator-declared month and withholds
the turning-three window while that month is undeclared, rather than defaulting to the
September its worked examples happen to use. Two typed diagnostics reach the operator
through the existing guardería collector: one naming the month to declare, one stating
that the cotizaciones cap is applied as supplied and is not bounded to it.

Both fire only for the turning-three population, and the cotizaciones one only where a
figure is actually declared — with none the cap already binds at zero for a reason the
operator can see. An advisory on every guardería filing would be noise, and noise is what
teaches operators to stop reading the channel.

The domain carries the disposition as a predicate with its reasoning attached, sited where
a successor would go to wire the limb, so the next reader meets the analysis rather than an
empty slot.

## Rationale

The knockout is that the authority is silent and the only alternative to silence is
invention. Declare-or-disclose already governs this box: where a value turns on a fact
only the operator holds, the application asks rather than assumes. The cotizaciones limb
is that rule one step further along — there is no derivable default at all, so disclosure
is not a weaker treatment than computation but the same treatment at the point where
computation is impossible.

The convergence with the prior author's judgement is evidence rather than reassurance.
Two readings of one article, arrived at independently and months apart, stopped at the
same line and both said so in writing. A boundary found twice by different routes is more
likely to be real than one argued once.

## Consequences

The measured over-grant on the window limb is closed, and the uncomputable one is visible.
An operator whose bounded figure differs from their annual total is now told, in terms
naming what to supply; before, they were silently over-granted.

The honest cost is that correctness on this limb now depends on an operator reading an
advisory and acting. That is weaker than an engine computing the bound, and this record
does not pretend otherwise. It is stronger than an engine computing a bound nobody
published.

The pathway this opens is option C: a per-child declaration would let the limb be computed
without inventing an attribution. The pitfall to guard is that someone reads the first
obstacle alone, performs the month-axis migration, and expects the limb to close. The
second obstacle survives that work, and this record says so where they will be looking.
