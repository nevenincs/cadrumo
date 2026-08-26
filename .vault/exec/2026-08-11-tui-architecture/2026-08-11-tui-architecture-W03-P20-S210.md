---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:71814c4a2c100ac23efdd8ddbbdb483cfde2cefa1d39441758cc104678605d31'
step_id: 'S210'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Privatize the loader implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`

## Changes

A src/cadrumo/domain/calculations/registry/_loader_internals.py
M src/cadrumo/domain/calculations/registry/loader.py
M 14 in-package consumers repointed onto the private implementation
M src/cadrumo/conftest.py
M dev/quality/registry_facade_family_census.v1.json

## Notes

Sixty-three symbols moved; loader.py keeps ten. The ten are not a judgement:
they are the closure of the six externally-required functions under incoming
references. Anything the internals would still reach stays on the contract
side, which is what makes the two modules acyclic.

A hand-picked boundary failed first. The loader has mutual recursion across the
contract line, so choosing the eight that looked right left the internals
calling a contract function. Computing the closure is the difference between a
split that works and one that cycles.

Two silent corruptions came from the extraction script and were caught before
commit. Classifying top-level statements by a single Name target dropped a
tuple assignment entirely, so the split must assert kept plus moved equals the
original count. Taking a block from the `def` line stripped four `@lru_cache`
decorators without any error, so extraction must start at the first decorator
and decorator counts must be diffed old against new.

The registry-tree memo is now reset through a named contract function, which
retires a cross-package private import the fixture had carried since before
this Step. `test_loader_cache_isolation` bound three names to the loader that
the loader only re-exported; each now names the module that defines it.
