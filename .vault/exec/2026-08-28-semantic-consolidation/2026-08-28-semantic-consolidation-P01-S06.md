---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:60c5c0f5a877edfb59b42cb2c265b8fdeec1d61bc35805fb77526721487314c2'
step_id: 'S06'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the domain/modelos lazy export map, repointing every consumer at the owning defining module

## Scope

- `src/cadrumo/domain/modelos/__init__.py`

## Changes

- `verify:` `src/cadrumo/domain/modelos/__init__.py` is inert: eleven lines, `__all__: tuple[str, ...] = ()`, no `__getattr__`

## Notes

No change needed. The step was already satisfied and had never been marked,
which is worth recording rather than quietly ticking: a plan that under-reports
its own completion distorts the only signal for whether the campaign is
finished. This was found by reading the plan's OPEN steps instead of adding more
to it -- `next_open_step` had been `P01.S06` for the whole campaign while
discovery-driven steps piled up behind it.

Its sibling P01.S80 stays open by design: it records that the retirement is held
uncommitted while a peer lands an overlapping application/modelo relocation,
because sixty files carry both diffs. That is a git-sequencing hold owned by the
session that manages commits, not work remaining here.

The other two namespace retirements are genuinely open and were not taken.
`adapters/persistence/storage/__init__.py` still carries its lazy map at 912
lines, and a peer is visibly editing it -- two probes this session hit that map
mid-write, once with the module absent and once with a duplicate namespace key.
`core/__init__.py` is 1236 lines with two `__getattr__` definitions and is the
largest slice.
