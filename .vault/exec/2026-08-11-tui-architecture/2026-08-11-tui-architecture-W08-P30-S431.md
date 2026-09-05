---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:6ebfc38c9278b9eccc12d35760b1ccf5260f8dd66e6ebe95798ce0b2a358aaf3'
step_id: 'S431'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Ground the M200/2024 casillas whose number occurs exactly once in the pinned record design, and hold the ones whose declaration contradicts it. The unlabelled casillas are not cosmetic: the modelo work-review screen resolves a label for every registry casilla and raises MissingTranslationError, so one absent label breaks the whole screen for this revision. Where a number appears once there is nothing to disambiguate, but casilla 00067 showed a declaration can name a section its own design does not put the number in, so accept a unique occurrence only when the declaration corroborates it and hold the rest.

## Scope

- `src/cadrumo/locales/*/modelo/schema/200.yml`
- `dev/locales/tests/test_casilla_label_matches_pinned_official_text.py`

## Changes

The unlabelled casillas turned out not to be cosmetic. The modelo work-review
screen resolves a label for every registry casilla, so ONE absent label raises
MissingTranslationError and the screen cannot render for M200/2024 at all. That
is what test_named_outlier_review_renders_every_registry_casilla[m200-2024] has
been failing on, and it reframes the remainder from tidiness to a broken screen.

Of the 82 that were left: 40 occur exactly once in the pinned design, 40 occur
several times, 2 do not occur at all. Where a number appears once there is
nothing to disambiguate, so the cell is the official label without needing an
adjudication to choose it.

Choosing is not all the pin was doing, though. Casilla 00067 showed a
declaration naming a section its own cited design does not put that number in,
and only the digest exposed it. So a unique occurrence was accepted here only
where the declaration's own section corroborates the design path. 28 agreed and
were written; 12 were HELD and are reported below rather than labelled.

Unlabelled casillas now: 82 -> 54 in es and en, 85 -> 57 in ca, 107 -> 79 in hu.
Casilla 00814, the one the work-review test names, resolves in all four.

## Notes

A GATE WAS WRITTEN FOR THIS COHORT AND WITHDRAWN, which is the more useful
result. It asserted that a uniquely-occurring casilla ships the design cell that
names it. Run against the corpus it failed on 701 labels: of 2480
uniquely-occurring labelled casillas, 1779 match exactly, 67 differ only in
whitespace, 381 are ellipsis-truncated, and 253 are deliberately shortened
(00096 ships "Innovacion tecnologica (IT). Deduccion pendiente/generada" where
the design reads the full "Deducc. para incentivar determ.actividades - 2024
Innovacion tecnologica (IT) - Deduccion pendiente/generada").

So the rule describes labels written under it, not a project invariant, and the
gate would have asserted a convention the project never followed against 701
labels nobody claims are wrong. It was deleted rather than narrowed, with the
measurement kept beside the surviving gate so the idea is not re-attempted
blind. The pin remains the single grounding mechanism, because it is an explicit
per-casilla commitment rather than a derivation.

CONSEQUENCE, STATED PLAINLY: these 28 labels are grounded -- each is the only
cell in the layout authority naming its casilla, and each agrees with its
declaration -- but they are NOT covered by a pin, so no gate asserts them. The
durable fix is 28 adjudication entries carrying official_label_sha256, which
would bring them under the existing gate. Appending to a filing-grade
adjudication ledger is a grounding claim rather than a locale edit, so it is
left for an explicit decision rather than taken here.

STILL BLOCKED: 54 casillas. 40 occur several times in the design and need a pin
to choose among them; 2 do not occur at all; 12 have a unique occurrence their
declaration contradicts, including 01264/01265/01266 (declared "2025 innovacion
tecnologica (IT)", design "del Club Natacio Barcelona (CNB)" -- the same three
whose existing pin matches no cell) and 01683/01684/01685 (declared 2026, design
2025). The work-review screen stays broken for M200/2024 until these are
adjudicated.
