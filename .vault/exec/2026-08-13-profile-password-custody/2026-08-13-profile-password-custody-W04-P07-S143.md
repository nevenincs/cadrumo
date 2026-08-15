---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:9bb06813850603b48917da5073818de3c8ad004f3931be3d293cf6ea8ceaf9e1'
step_id: 'S143'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule where companion distributions built from this repository live, since two established companions sit under one directory and a third was placed elsewhere, which is one concept in two homes and the fragmentation this campaign exists to remove

## Scope

- `pyproject.toml`

## Description

- Establish the three distributions this repository builds beside the core, by
  path and by distribution name, rather than accepting the row's premise.
- Rule the home on the one criterion that actually separates them, and record
  the rule where the three are wired.

## Outcome

The three are named, and the row's premise does not survive contact with them.

Two sit under one directory: `cadrumo-data-manuals` at
`packaging/cadrumo_data_manuals` and `cadrumo-data-official` at
`packaging/cadrumo_data_official`. The third, `cadrumo-harness`, sits at
`src/cadrumo-harness`. So the arithmetic in the row is right.

**But they are not one concept in two homes.** Each data companion owns NO
source. It is a project file, a licence pair, a README and a hatchling build
hook, and every byte it ships is force-included out of the ONE corpus tree the
core package owns, remapped under a mirrored namespace. It authors nothing; it
repackages. The harness owns a real source tree - modules, colocated test
suites, and its own console script - and nothing force-includes it from
anywhere.

That is the criterion, and it is not "companion": **does the distribution own
Python source?** Owning source puts it under `src/`, beside the core source
tree, named for the distribution. Owning none puts it under `packaging/`, where
its neighbours are the Homebrew formula generator, the Scoop manifest
generator, the MCPB bundle builder and the marketplace scaffold - four more
recipes that emit an artefact from a tree they do not own. That shared job is
what the directory is for, and the two data companions are doing exactly it.

**So both existing placements are already correct and nothing moves.** The rule
is written into the root project file immediately above the source overrides
that wire all three, so the next distribution is placed by reading the same
lines that resolve it. It states the criterion, assigns each of the three, fixes
the directory-name convention (hyphenated under `src/` matching the
distribution, snake under `packaging/` matching the emitted import namespace),
and closes the question the row was really asking: there is no third home and
nothing belongs at the repository root.

The distribution names were checked against the product-identity discipline as
part of the ruling. All four are `cadrumo`-prefixed; the sole human executable
is `aeat` on the core; the only other console script anywhere is `cadrumo-mcp`,
declared by the harness. Nothing retains `aeat` as a product import, namespace
or owner, and nothing exposes `cadrumo` as a second human executable.

## Notes

**The ruling is a comment and carries no gate of its own, which is a deliberate
limit and is stated rather than left to be discovered.** Two shipped gates
already pin the harness's location by literal path - the console-script gate
reads its project file from `src/cadrumo-harness`, and the import-edge census
asserts the harness distribution is one of the trees it spans - so a move would
red the tree today. Nothing equivalently pins the two data companions to
`packaging/`, and this row's scope was the project file alone, so no gate was
added for them.

Naming the criterion is what makes the rule durable, and it is the part the row
could not supply: "two companions here, one there" reads as fragmentation only
until someone asks what the two have in common that the third does not. The
answer is that they have no source, and it decides every future case without
another ruling.
