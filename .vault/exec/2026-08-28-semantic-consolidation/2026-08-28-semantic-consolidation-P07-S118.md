---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:3ea971351f3b306b9a461299b275f1cf7a9fb1517a19c93e99ee2e6a1a457425'
step_id: 'S118'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Publicise the mirror-manifest module so its remote-naming contracts are reachable without going through the storage namespace

## Scope

- `src/cadrumo/adapters/outbound/storage/`

## Changes

- `R` `adapters/outbound/storage/_mirror_manifest.py` -> `mirror_manifest.py`, 6 consumers repointed
- `verify:` no reference to `_mirror_manifest` remains in `src/` or `dev/`
- `verify:` the remote-naming contracts resolve at a public module without going through the storage namespace

## Notes

The step asked for the mirror-manifest module to be publicised so its
remote-naming contracts are reachable without the storage namespace. It was
blocked for most of this campaign, and not by difficulty: the storage namespace
had already been retired under `P01.S07`, which left two consumers in
`entrypoints/cli/_config` importing from a private module in another package --
trading the facade violation for the boundary violation.

The operator ruled that private defining modules may hard-move to public names,
deleting the private path in the same change. That is what
`aeat-architecture-boundaries` prescribes and it is what closed this step.

This was one of 152 promotions made under that ruling. The measured effect
across the campaign: cross-package private imports fell from 208 modules over
646 consumer files to 49 over 65.

### Four consumer shapes, three of which no import scan sees

The promotion tool learned each of these the hard way, and each is recorded
because the next relocation will meet them again:

- `from pkg import _mod` binds the MODULE by name, so the resolved import target
  is the PACKAGE. Matching only the module misses it; matching the bare module
  name over-applies to identically named modules elsewhere -- both mistakes were
  made, in that order.
- The error-code registry keys `CadrumoError` subclasses by fully-qualified
  module path and refuses an unregistered subclass at import time. Every
  promotion of a module holding one is also a registry edit.
- A plain string replacement of the dotted path also rewrites LONGER module
  names sharing the prefix. Promoting `_m303_regimen_simplificado` silently
  repointed `_m303_regimen_simplificado_annual_summary`, which still had its
  underscore. The replacement is now anchored on a non-identifier boundary.
- The repo-root `conftest.py` imports from `cadrumo.tests`, and a `src/`-and-
  `dev/`-only sweep leaves it on the pre-promotion name, breaking collection
  tree-wide from outside both scanned roots.
