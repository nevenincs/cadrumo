---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-26'
step_id: 'S01'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---

# Land the non-raising inner-envelope equality predicate in the storage substrate beside the existing lineage policy, exported through the storage package facade, leaving ensure_schema_version_readable deliberately absent from that facade because it is the layer-one gate

## Scope

- `src/cadrumo/adapters/persistence/storage/`

## Description

One shared non-raising predicate deriving the inner-envelope comparison from the
namespace constant, consumed through the storage package facade, with layer one's
`ensure_schema_version_readable` kept deliberately absent from that facade so a
layer-two caller cannot reach for the wrong gate.

## Outcome

Delivered by a peer agent in commit `a8a29fdbe1`, not by this record's author.
Recorded here because the step is closed and the closure rests on verification
rather than on trust.

Verified at HEAD: `inner_envelope_version_is_current` exists in
`_schema_lineage.py`, is exported from the storage facade, and is non-raising as
the ruling required. Its module docstring now carries the layer-one / layer-two
distinction and the below-current teeth argument, so the reasoning survives in
the code rather than only in the decision record.

The non-raising property is the constraint that mattered, not a stylistic
preference, and it was honoured — see S02.

## Notes

This step was in flight as uncommitted peer WIP at the moment the plan was
authored, which is why it was not taken up directly: editing those files would
have collided with a live peer mid-write.
