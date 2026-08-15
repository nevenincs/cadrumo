---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e733592967169bbed17790acdb97940d94d469bd87c9599bccae704fb02adbc8'
step_id: 'S87'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh stop the configuration-reset retention decision failing OPEN when no assessment is supplied

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Establish whether the unassessed state is reachable before guarding against it.
- Revert the guard already built once the state proved unrepresentable.
- Leave behind what actually prevents the next misreading.

## Outcome

**REFUTED. The branch is not fail-open, and the row's premise was wrong.**

The deletion assessment carries a model validator that constrains BOTH
directions: an existing target requires its label, fingerprint and retention
assessment together, and an absent target may carry none of them. So a target
that exists cannot carry a missing retention assessment at all -- the unsafe
state is unrepresentable, enforced by the type rather than by a runtime check,
which is the stronger guarantee.

Reaching the unassessed branch therefore means the target does not exist, and
"nothing is retained" is a TRUE statement about that target rather than a
decision taken without evidence. Confirmed three ways rather than read once:
constructing the forbidden shape raises, no construction bypass exists anywhere
on that model, and the single production construction site builds only the absent
form.

The guard had already been built when the refutation landed, and all of it was
reverted: a new error class, its registry entry, guards at both call sites, and
four locale strings removed through the catalogue CLI. Shipping it would have
added an unreachable guard, an error code and four translations for a branch that
cannot execute -- and worse, would have implied the rule lives in that function
rather than in the type, so a later refactor could have moved the function and
lost the real protection while keeping the decorative one.

What landed instead is a comment. The branch has now been misread as a missing
guard twice, and cost a full investigation each time; a comment that stops the
third reader is the entire remedy.

## Notes

The dispatcher endorsed the original finding with more confidence than the
evidence supported, calling it this campaign's signature defect on a destructive
path and opening this row on that basis. That amplification is part of the record:
an agent reported a plausible defect, the dispatcher agreed without asking the
reachability question, and the row existed for hours before the author refuted
their own finding.

**The transferable rule: reachability is the FIRST question for a fail-open
claim, not the last.** A branch that decides something permissive is only a defect
if control can arrive there in the state it assumes. Asking that before asking
what the branch does would have closed this in minutes rather than an
investigation, a built fix, and a revert.

The second lesson is about where an invariant lives. This one is enforced at the
boundary that constructs the record, so no call site can violate it and no call
site needs to check it. A type that makes an unsafe state unrepresentable looks,
from any single consumer, exactly like a missing guard -- which is precisely why
it was misread twice, and why the remedy is a pointer at the type rather than a
guard beside the reader.
