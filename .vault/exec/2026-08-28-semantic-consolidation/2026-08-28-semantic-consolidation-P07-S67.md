---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6b445723b55cfe475b96bf1374441b6332b3ac69d5b030e7a85f0eecedc254eb'
step_id: 'S67'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Relocate the production code out of the overview, contribuyente and core errors namespaces, which define it directly and cannot be made inert by deleting a map

## Scope

- `src/cadrumo/`

## Changes

- `verify:` `application/overview`, `domain/contribuyente` and `core/errors` all declare `__all__: tuple[str, ...] = ()` and define nothing
- `verify:` the contribuyente relocations are recorded under `P07.S167`

## Notes

All three namespaces named by the step now define no production code and are
inert.

`domain/contribuyente` was closed here by relocating its two defining
subpackages -- `inventory` to `records.py` (58 symbols) and `assets` to
`records.py` (11 symbols) -- under `P07.S167`. `application/overview` and
`core/errors` were emptied by other lanes; the committed history carries
`relocation:core.errors split the errors namespace into its canonical defining
modules` from another session.

Confirmed against the live tree rather than against that history, because a
namespace can be emptied and refilled: each of the three was read for its
current definition count and its `__all__`, and all three are inert now.
