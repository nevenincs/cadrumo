---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:56062018691c6bf592b25839ec47567448126549d95a9dc97f0e10333cdd51f6'
step_id: 'S07'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the storage lazy export map last of its subtree, repointing its core, custody and crypto facing entries

## Scope

- `src/cadrumo/adapters/persistence/storage/__init__.py`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/__init__.py` -- 257 lazy exports retired, namespace inert
- `M` 326 consumers repointed at the 33 modules that define the symbols
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_smoke.py`
- `M` three cross-root consumers (harness, dev) moved to absolute imports
- `verify:` `pytest adapters/persistence/storage -n 0 -m ""` -> 1222 passed, 0 import failures
- `verify:` `--collect-only` -> 28950 collected, 6 errors, all pre-existing and peer-owned

## Notes

The largest facade in the tree, and the one every other storage retirement was
waiting on: `blob_store`, `envelope`, `bucket`, `master_key` and `sql` could not
go inert while their parent read its own exports through them.

Resolution was done ONCE, to an absolute module per name, and each consumer then
got a relative import whose depth was computed from its own position. That is
the opposite of what the earlier repointings did -- they adjusted the existing
path, which is how a `..` became a `...` and how a consumer's own module segment
ended up concatenated onto a forwarded path. Deriving beats adjusting.

### Three consumer shapes an AST import scan cannot see

Each surfaced only under a real test run, after `--collect-only` was clean.

- **String module paths.** The map itself is `name -> "..module"`. Retiring
  `core.classification` earlier had already broken this file through five string
  entries the rewrite left behind, because they are data rather than imports.
- **A different distribution.** `dev/` and `src/cadrumo-harness/` are separate
  package roots. Their module names do not begin with `cadrumo`, so a relative
  import computed against them escapes their own root. They take the absolute
  form; the tool now decides on the root, not on the path.
- **Source inside a string literal.** A subprocess test embeds a Python program
  as a string and runs it in a child. Its imports are invisible to every static
  tool and it fails only when the child runs.

### A gate whose premise the ruling reverses

`test_runtime_master_key_and_namespace_boundaries_are_public` asserted, in its
own docstring, that "critical storage boundaries must be imported from the
package root" -- precisely what this step retires. That is a contradiction
between a gate and a ruling, not a bug to patch quietly.

What the gate PROTECTS survives the ruling: those boundaries must stay public,
named and reachable. So it now resolves each of the eleven against the module
that defines it and additionally asserts the root exports nothing. It is a
stronger check than before -- it pins each boundary to ONE canonical module
rather than to a re-export that could have come from anywhere.

### What was deliberately left broken

Four consumers name symbols that no longer exist anywhere in the tree
(`get_master_key_provider`, `StoragePathKind`, and two dunder reads). Those are
half-landed peer relocations and were already failing. Their imports were left
pointing where they pointed, so they are exactly as broken as they were found
rather than blocking this retirement on someone else's incomplete work.
