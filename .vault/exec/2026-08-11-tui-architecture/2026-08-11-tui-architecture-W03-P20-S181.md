---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1b1ffcbb8b4adb3d1c89f889ff5b5997229ed23b663b2207c06f4bbf96cd2685'
step_id: 'S181'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retain bindings as public only for locally defined contract symbols and direct-import every borrowed owner

## Scope

- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py -n0` -> `pass`

## Notes

No source change was needed: the hard move from `src/cadrumo/domain/calculations/registry/_bindings.py` already
landed and the private module is gone. What was missing was a gate holding it
there, which `test_keep_public_family.py` now does per row - the retired path
must be absent AND unimportable, so a reintroduced private module reds this
row specifically rather than passing for being merely unused.

The surviving owner is asserted from the row's terminal destinations rather
than its `new_path`, because a family that moved out of the registry entirely
leaves a `new_path` nothing occupies.

## Correction

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/application/aggregation/__init__.py`

The earlier pass recorded that no source change was needed, which was true of
the hard move only. `bindings` still exported seventy-five names, fifty-nine of
them borrowed from their true owners, so it remained a re-export facade. The
export list now holds the sixteen locally defined contract symbols.

One consumer genuinely borrowed through the facade: `WithholdingObservation`,
repointed to `withholding_bindings`. Removing the export list left imports that
existed only to re-export, which ruff removed.

Verified: every production module still imports; no consumer reaches a removed
name by absolute, relative, aliased, module-attribute or string form; the
public-API boundary test asserts these names are absent from the package
namespace, which this strengthens.
