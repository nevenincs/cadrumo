---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S33'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Rule on whether a schema-required profile field may be cleared or left never-set after creation, the completeness check keying on fact presence rather than value presence while the overview beside it already keys on value, and place the guard where the state is created rather than at each consumer

## Scope

- `src/cadrumo/application/user_profile/_validation.py`
- `src/cadrumo/application/user_profile/_commands.py`
- `src/cadrumo/application/user_profile/_orchestration.py`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py`
- `src/cadrumo/application/user_profile/tests/test_required_field_presence_is_value_bearing.py`
- `src/cadrumo/adapters/inbound/tui/tests/test_manager_required_field_refusal.py`
- `src/cadrumo/application/auth/tests/test_blank_profile_identity_refusal.py`
- `src/cadrumo/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`

## Description

Assess the two questions first, by execution rather than by reading, and rule
before implementing.

Make the completeness check's presence predicate value-bearing rather than
existence-bearing, so a cleared required field is missing exactly as an absent
one is.

Refuse a blank submission on a required field at the edit dialog, using the
required flag the view model already carries.

Report a write-door refusal in a notice line instead of raising it through the
screen.

Correct the early-mint docstrings to state what the registration arm does
rather than what it was believed to do.

Rebuild the peer identity-refusal fixture below the validated edit door, which
now refuses the clear it used to construct.

## Outcome

The defect was one predicate and it was worse than the brief framed it.
Presence was computed from a fact EXISTING, while the line immediately below
already filtered on the value being present. A cleared field is a fact whose
value is empty, so clearing a required field did not evade the completeness
check — it SATISFIED it. Measured directly: with the fiscal identity set, the
other singleton required field is reported missing; adding a CLEARED fact for
that same field made the report disappear. A requirement was affirmatively
satisfiable with nothing, which makes a clear strictly more dangerous than
never setting the field, since never setting it at least raises.

The corrected predicate was not new logic. The overview built from the same
record already computed the right one to decide which fields to show the
operator as missing. The enforcing surface and the display surface disagreed
about what present means and the display one was right, so the fix was a
validator adopting the predicate rendered beside it. A parametrised test now
pins the two together for both ways a value can be empty.

Two questions were settled before any code changed. Refusing the clear is
correct in general, and the early-setup blast radius does not exist: the edit
door already skips completeness wholesale for a profile still in setup, so the
change cannot bite that arm by construction, and the relaxation was never what
let the clear through for a promoted profile — the presence-keying was. The
reachable operator route was found and is ordinary rather than exotic: the
manager builds a fact from the submitted text stripped to nothing, so a blank
box on any listed field is a clear, and the page lists every declared field.

The registration arm's reservation claim was aspirational and nothing had been
lost. The uniqueness enforcement is real, but the setup flow's first persist
contributes no fact for an unanswered or blank identity page, so a mint before
that answer supplies nothing to compare and deferred completeness raises
nothing. A history search for the claim returns only the commit that introduced
the arm, and that commit added no identity logic. It was never enforced there,
so the docstrings now say what the code does. Whether that arm should reserve
the identity is a product question and was deliberately left open.

Evidence. Eight unit tests and four integration tests, all passing. The
mutation proof was performed rather than asserted: putting the superseded
predicate back reds six of the eight, with the restore in a finally block and
the byte-for-byte restoration verified afterwards, so an interrupted run
cannot strand a broken file for every other agent in this tree. One of the
eight recomputes the superseded rule inline as a control, so the suite states
its divergence from the old rule rather than merely depending on it. The
optional-field integration test is what keeps the guard narrow: without it the
blank-clears behaviour could be lost wholesale and the required-field tests
would still pass. Surrounding suites at the landing commit: 681 passed across
profile, terminal and wizard; 221 passed across auth; 185 passed across
locales, terminal and the new units. Catalogue parity clean across all four
languages.

## Notes

One fix was not in the ruling and the ruling would have shipped a crash
without it. The manager's write path did not catch, so once completeness bound
on a promoted profile a door refusal would have taken the whole screen down —
and it would have done so for exactly the operator the change exists to
protect, the one who just blanked a required field. Refusals now report in a
notice line, which is the reasoning the action buttons already carried applied
to the half that lacked it. It was found by asking what the enforcement change
altered downstream rather than only whether it was correct.

The input guard was placed one layer above where the ruling named it. The
frontend that builds the fact holds only a path and a value, so guarding there
means loading the schema in the entrypoint layer to re-derive a flag the
screen already carries and already renders as the required mark. The guard
sits at the operator's empty box, using what was already there.

The whitespace residual is recorded as a divergence rather than a gap. No test
asserts a whitespace-only value fails the validator, because the validator
matches the overview's emptiness test rather than stripping; making it strip
would make it stricter than the overview and break the consistency the whole
ruling rests on. Whitespace is refused at the input boundary instead and has
an integration test there. The fuller truth is that the surfaces genuinely
diverge: the censal ownership guard DOES strip, so a whitespace-only fiscal
identity would satisfy the validator and the overview and be refused by the
censal read. That divergence fails safe — the strict surface is the one
guarding a live authority read, the permissive ones only report completeness —
and no shipped writer can persist such a value anyway.

The surface-agreement test asserts only that the fiscal identity appears as
missing on both surfaces, not that their full missing sets are equal. This is
deliberate and worth knowing for the two follow-on items about required fields
on repeatable rows: the display surface counts every required field including
the thirteen that belong to repeatable rows, while the enforcing check skips
those entirely. Full-set equality would have frozen that discrepancy as a
gate, so nobody reconciling the two surfaces has to fight this test to do it.

One peer regression was absorbed rather than deferred. A sweep proving that no
authentication provider binds a session against a blank profile identity built
its fixture by clearing the identity through the validated edit door, which
this change refuses, so three of its five went red. Its subject is the guards
refusing that state if it is reached some OTHER way, so the fixture now reaches
it another way, below the validated door, and asserts that the clear actually
took — without that assertion the fixture could silently test nothing. The
sweep itself is unchanged and the file was clean when edited.

Two findings were deliberately kept out. Thirteen of the fifteen required
fields are row-fields of repeatable sections, which the completeness check
skips entirely, so only two are reached by it at all; and the display surface
counts all fifteen. Both predate this change, the display module was not
touched here, and folding either in would have turned a one-line correction
into a redesign of what required means on a repeatable row.
