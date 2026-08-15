---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S147'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh retire the manifest digest field from the bucket deletion contract and complete the retirement half of the deletion supersession

## Scope

- `src/cadrumo/application/_bucket_deletion_contracts.py and src/cadrumo/application/config_reset.py`

## Description

- Retire the one field on the coverage checklist with no live source.
- Verify nothing on disk carries it before removing it.

## Outcome

The field is retired and the coverage checklist is closed. Every remaining field
has a live source: the identity, the existence check, the three inventory facts,
the retention flag, and — from the preceding step — the retained count, the
floor and the safe-erase date.

The ruling was verified before it was acted on rather than taken: the field had
zero production constructions, and the only two in the tree were hand-built
fixtures. A field only tests could fill, describing an artefact only history
contains.

**Scoping it narrowly is what kept the change correct.** The same name denotes
at least four unrelated live things here — a sealed archive header, the
blob-store manifest, the corpus bundle, and the export and inspect results — so
a sweep by name would have taken all of them. Each other site's owning model was
checked before being left alone. That is the fifth time this campaign's
overloaded vocabulary has nearly cost something, and the first where the cost
would have been a deletion rather than a wrong count.

Nothing is stranded, checked rather than assumed: the field is persisted inside
the reset journal, and no reset journal exists anywhere under the storage root.
A journal carrying it would now be refused by the strict model rather than
tolerated, which is the posture the pre-release rule asks for.

## Notes

**The closed checklist is not a green light, and the step says so.** The
contract is now fully answerable while its producer still refuses every existing
target, because nothing has yet wired the filing retention assessment into the
deletion preflight. That single unwired hop is the sole cause of fifteen failing
recovery and concurrency modules — traced to a subprocess rather than inferred,
with none of the failures naming the retired field.

So the supersession's remaining blocker moved from the contract's SHAPE to a
missing connection, which is a materially smaller and better-specified thing
than it was two steps ago. It is rowed separately rather than absorbed, because
removing a producer's refusal is a change to what guards a destructive path and
should not ride inside a field retirement.
