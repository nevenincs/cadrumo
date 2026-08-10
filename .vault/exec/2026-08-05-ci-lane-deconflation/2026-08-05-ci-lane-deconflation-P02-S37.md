---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c983ebcaa4e6c534d95f68d8b7000ac57b7cc467eb783a189b2692b5dfa9dfb2'
step_id: 'S37'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Restore the operator-settable storage root to the root help document

## Scope

- `src/cadrumo/application/operator_surface/_help.py`
- `src/cadrumo/locales/`
- `src/cadrumo/application/operator_surface/tests/test_contract.py`

## Outcome

Closed at `6305cdfb7f`. **The four-catalogue locale work this row was scoped around was never needed**, and that is the finding rather than a footnote - a row that vanishes without a record is indistinguishable from one nobody did.

The row assumed that restoring the mention to the root landing meant minting a root-scoped translation key, which would have required real Catalan and Hungarian strings through the locales CLI. An agent must not invent those: a fabricated translation is a defect shipped in a language nobody here can verify, and it is invisible in a way an untranslated string is not. So the row was correctly gated on an operator.

It was gated on a premise that did not hold. The sentence naming the settable variables already exists as a translated key on the CONFIG document, present in all four catalogues. Rendering that same key in the root document closes the regression with zero new strings, no honesty-ratchet exposure, and one canonical sentence shared between two documents rather than two that drift apart. A shared key is better than a duplicated one, and here it was also the only path that did not need a human.

The assertions returned to `root_text` carrying their reasoning inline, so the next reader who finds them stale asks whether the content was **entitled** to move before following it.

## Notes

This row exists because of a defect I introduced. Commit `09fe7d4588` moved those assertions to the config document after measuring, correctly, that the help content had relocated - and inferred that the assertion should follow. The relocation WAS the regression: the variable is live and settings-bound, and its own documentation states that a developer wanting the store inside their checkout sets it. So the test then passed over a live defect with a correct-looking measurement behind it, which is strictly harder to doubt than a green backed by nothing.

Rowing that correction was necessary and not sufficient. The row recorded the debt while the false signal kept being emitted, and under a no-false-green directive that is not an acceptable interim state. **The row is not the fix while the green is still lit.**

What closed it was fixing the surface rather than the assertion. Loosening or relocating the assertion would have been re-labelling: the defect was that a live operator-settable knob had left the surface an operator reaches first, and only putting it back addresses that. Discoverability of a settable knob is part of the surface, not decoration on it, and this operator is frequently an autonomous agent holding only the help text and the envelope - it cannot infer a variable from convention or ask a colleague.

The change widens rendered root help by one paragraph, which is a shared surface. That was flagged to the test-run authority explicitly rather than submitted as a request for a pass, because a fourteen-line diff reads as trivial and the surface it touches is not. Three inspections came back finding no covering gate: the schema-size ceiling does not have help text in scope, no gate counts occurrences of a locale key, and `root_text` is referenced nowhere outside this package. The flag landed on an empty set, which is the right outcome for a flag rather than a reason not to raise one.
