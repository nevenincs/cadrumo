---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:1f4423ed89207888c7cd340165a09199f4764cf11a6bdeb4bb3eee258b77253b'
step_id: 'S56'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh close the fourth unjudged profile-fact door, which promotes a record to complete setup state without validating it

## Scope

- `src/cadrumo/application/user_profile/_profile_record_repository.py`

## Description

- Establish what the promotion boundary actually sees before choosing a
  strictness, rather than copying the strictness of the adjacent door.
- Judge the record against the profile schema at promotion, in full.
- Convert the production assertion on the neighbouring write path into a typed
  refusal.

## Outcome

Promotion now judges HARDER than the fact-writing doors: it demands completeness
where the censal and wizard doors deliberately defer it. The ruling is grounded
in a contract that already existed and was simply not honoured -- the validation
module's own documentation states that a profile born incomplete defers exactly
these checks and that the lifecycle re-applies them IN FULL at promotion. The
code had never done so.

The reasoning recorded is that completion is not a label for a record that
stopped being edited; it is the claim that nothing required is missing. An
invalid record that merely exists is contained. An invalid record wearing the
completed state is trusted by everything downstream, and filing readiness keys
off exactly that.

One deliberate ordering choice: the already-complete early return stays AHEAD of
the judgement, because it publishes nothing, and holding an idempotent no-op to a
contract a stored record may predate would refuse a caller that changes no state.

Severity was measured rather than assumed, and the measurement lowered it. The
promotion method has NO production caller today -- only tests reach it -- so this
is dead capacity carrying an open hole rather than a live exploited defect. The
door is documented as intended for a setup-commit path not yet built. Saying so
plainly is what makes the record honest about why this was worth doing anyway.

Verified independently: 4 passed, and the five directly affected modules run 40
passed sequentially.

## Notes

The bite proof for a maximally strict door needs a different shape from the
opposite-direction pair used on the adjacent step, and the author found the right
one rather than manufacturing a mirror. Removing the judgement reds two tests;
keeping the judgement but relaxing its strictness setting reds the SAME two. That
second proof is what demonstrates the strictness itself is load-bearing rather
than merely that a call exists -- that this is the stronger check and not the
neighbouring door copied. An over-hardened direction was deliberately NOT
invented, because full strictness is the correct setting here.

The two refusal tests fail for deliberately different reasons, one on an
unconditional required field and one on a conditional block opened by an answer,
so a door re-applying only half the completeness rules still reds.

A latent hazard was found and left alone with reasons: the persisted record's
setup-state field DEFAULTS to the completed value, so a record constructed
without stating it silently claims completion. All three production construction
sites state it explicitly, verified by syntax-tree inspection rather than by
search, which makes this latent rather than live. Changing a persisted model's
default is a shape change and is carried as its own row.

Two further prose defects were corrected, both of the class this campaign keeps
finding: documentation pointing at a method on the wrong class, and
documentation naming a function that exists nowhere in the tree.

The production assertion on the neighbouring write path is now a typed conflict
refusal. The invariant is worth keeping -- a commit that did not advance the
revision by exactly one means the record published is not the record read -- but
not as something stripped under optimised interpretation that reaches an operator
as a bare assertion error.

A canonical complete-profile fact set was added to the shared test support,
derived by asking the validator what it still reports missing rather than
hand-listed. A hand-listed set would have been a second authority for the
schema's required flags: the moment the schema gains one, every profile built
from the literal is quietly short of complete while still calling itself
complete.
