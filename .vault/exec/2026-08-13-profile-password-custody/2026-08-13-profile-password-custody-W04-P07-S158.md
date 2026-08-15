---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:868417f510bea9787f62fab7d91ca6ef4875b9715ca848eacb97c82f60d71ffa'
step_id: 'S158'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium remove the duplicate bundle schema version literal on the portable export model, which defaults to a bare three while its own named constant declares three in the module beside it, so an already-enrolled format states its current version twice with nothing comparing them, this being the smallest instance of the double-declaration class and the one whose correct shape already exists to copy

## Scope

- `src/cadrumo/application/user_profile/_bundle.py`

## Description

- Remove the model default rather than pointing it at the constant.
- Stamp the version at the one production construction site.
- Assert the absence of a default so it cannot return.

## Outcome

**The duplication was the smaller half of what this row fixed.** The model
default was also silent read-tolerance: a payload carrying no version at all
validated as whichever number happened to sit in the model, so a bundle nothing
wrote would have parsed as current. That is the refuse-do-not-tolerate rule
being violated by a field that looked like a harmless default, and it is the
ground that justifies the change on its own. The second declaration is real but
secondary.

So the fix is not the one the row proposed. Pointing the default at the constant
would have left the tolerance untouched and merely made the two numbers agree.
The field is now **required with no default**: absent must refuse.

**Ownership stayed in the application layer, and the steer that sent this row
there pointed the other way.** The instruction was to prefer the domain, since
this project keeps domain logic independent of adapters and a model reading its
version from a persistence concern is the wrong direction. The evidence
overrode it. The current write version, the durability floor, the one-hop
upgrader table and the accepted-version set are **one lineage unit**, and the
compatibility regime requires a version bump to land its upgrader in the same
change. Moving the current version to the module that declares the record shape
would have split one atomic obligation across two layers. The layering
principle was tested here and lost, and that is recorded so the next reader does
not re-apply it and undo this.

There is exactly one production construction site, which now passes the constant
explicitly. Every other construction is a test.

**Removing the docstring line that restated the supported version is its own
move, not tidying.** Which versions are accepted is the lineage's decision, not
the model's, and a docstring restating a fact owned elsewhere is the same defect
class as the second literal expressed in prose. This campaign has repeatedly
found a restatement being read as current long after it stopped being true.

Nine test call sites carry one named fixture constant per module rather than
nine literals, and the constant's comment states that it pins the shape under
test and claims nothing about what production stamps. The tests deliberately do
not import the application constant: that would rebuild in the test layer the
coupling the change removes, and a detector for the two disagreeing is rowed
separately.

The guard is asserted rather than implied — a test proves the field is required
and that an unstamped payload refuses. A reader who sees a required field looks
for who stamps it; a reader who sees a default assumes it is the answer.

## Notes

Verified at nine passing standalone on the schema module, with the two portable
export modules green at fourteen.

**A wider run over the application user-profile suite shows failures that are
attributed rather than left beside a green module.** Seven share one ambient
cause: a registry validation error naming twelve enrolled modelo layout sources
that declare layout authority over bundled orden files carrying no annex — a
peer's evidence-tier work, unrelated to versions or bundles.

An eighth, in the login handover crash-recovery parametrisation, **did not run
at all** in the first attempt: those cases are integration-marked and the
default marker expression dropped sixty-six tests silently. Run explicitly it
passes at twenty-eight. It is NOT recorded as spurious — in a tree with active
peers a clean re-run cannot distinguish a transient from a repair that landed in
between, and a peer commit declaring the resumed bucket key a wipeable buffer
touches exactly that path. Repaired-in-between is at least as likely as
transient, and which one cannot be settled without the other run's HEAD.

**A capture hazard worth filing.** Most of this work reached HEAD inside a
peer's broad registry-sweep commit rather than under its own message; what was
committed here directly is only the residue those captures missed. Beyond the
attribution cost, there is a sharper one: **if such a sweep commit is ever
reverted, it takes this work with it, and nothing in that commit's message would
warn whoever reverts.** Four captures occurred in one day.
