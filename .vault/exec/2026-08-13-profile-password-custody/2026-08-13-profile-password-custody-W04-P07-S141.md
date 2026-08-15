---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:4364c8c604d7b4c099bdbdf77788cdc55a05c046fa147890a8d655d9d6ed41d9'
step_id: 'S141'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh complete the half-landed harness extraction that currently breaks collection tree-wide

## Scope

- `pyproject.toml and src/cadrumo/entrypoints/`

## Description

- Establish from precedent whether the extracted package is a workspace member
  or a path dependency, rather than from whatever silences the error.
- Wire it, repoint every consumer, and state which decisions were not made.

## Outcome

Collection is restored: four tree-wide errors down to one, and the survivor is
an unrelated telemetry defect rowed separately.

A peer campaign had extracted the agent harness into its own package and landed
three quarters of the change. The new package was complete — its own project
file, licence, notice and source — but the root project referenced it nowhere,
so it was not importable; and six modules still imported the deleted package,
four in production and two in tests.

**The packaging question was answered by precedent, which is what makes the
answer defensible.** This tree already ships two companion distributions built
from the same repository, wired as pinned dependencies plus path sources with
identical build configuration. Introducing a workspace beside that would have
created a second packaging mechanism where one already had two users — the
fragmentation this campaign exists to remove, committed while repairing someone
else's. The harness is wired the same way as its two established siblings.

**That also reconciled the extraction's own wording rather than choosing between
readings of it.** Its message says "independently installable" and "out of the
core shipped package", which reads as optional. The data companions prove this
tree treats separate distribution and required dependency as compatible: they
are separate wheels AND hard dependencies. So the stated goal is satisfied by a
path dependency and no consumer had to be severed.

**One decision was deliberately not made, and is named rather than implied.**
The extraction's message says only what moved and nothing about its consumers,
so the four production surfaces were repointed at the new package **without a
decision behind whether the core should depend on the harness at all**. Those
four serve the harness to an agent; if they belong inside the harness package
too, this repair is the wrong shape and should be superseded rather than built
on. A repair that names the decision it did not make can be safely revisited.

Sweeping for consumers rather than accepting the four named in the dispatch
found two further test modules. Zero references to the deleted package remain.

## Notes

Two findings were flagged and deliberately not acted on.

The two established companion distributions live in one directory and this third
was placed in another. That is one concept in two homes, and it is rowed —
relocating another campaign's package mid-extraction would have been exactly the
second-writer collision this campaign has spent the session avoiding.

The surviving collection error is a telemetry producer test importing a private
helper from a sibling TEST module, where the helper was removed rather than
renamed and no equivalent survives. The shape is worth ruling on beyond the
repair: a test module importing another test module's private helper is fragile
by construction.

The package was installed editable into the shared environment to unblock every
agent, since the declaration alone does not make it importable. That is a side
effect outside the author's worktree and was declared rather than left to be
discovered — with the open question of whether a clean dependency sync now
reproduces it from the declaration, since a shared environment holding state the
project file does not describe is invisible until someone rebuilds.

## Correction

The decision this record describes as "deliberately not made" **had been made**,
and was found shortly afterwards in the extracted package's own project file:

> cadrumo-harness is a consumer of the cadrumo CLI/library, never the reverse
> … cadrumo itself carries no dependency on this package.

So the four entrypoint surfaces were not meant to survive importing it. The
repair added exactly the reverse edge that comment forbids and closed a
dependency cycle between the two distributions. The proper shape is to move
those four harness-delivery surfaces into the harness package and drop core's
dependency, which is rowed separately; this repair and its lock regeneration are
a deliberate temporary that the sever supersedes.

**The search that missed it is the transferable part.** The commit message was
searched, found silent, and silence was read as absence. The statement was in
the new package's project file — one section below the build configuration
already opened twice for other reasons. **A relocation's rationale can live in
the artefact it creates rather than in the commit that creates it**, and a
silent commit is not evidence of a silent author.

This campaign has repeatedly met the inverse — a comment asserting something the
code does not do. This is the first instance of a correct and load-bearing
statement sitting unread in exactly the file everyone was already in.

A second defect surfaced from the same thread and is fixed. The lock carried no
entry for the new package while the project file declared one, so the
environment held it only because it had been installed by hand: a frozen sync
would have failed, and a local sync would have UNINSTALLED it and re-broken
collection. The environment was standing on a manual step nobody else knew
about, and the next person to sync would have appeared to break it.
