---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:fffc09da093aec6480dbf13e27205feb67578f1a77c91a055a1eaba1096bd4d8'
step_id: 'S158'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Make the retirement sweep survive a peer's concurrent rename, then repoint the two stale gate pins it found and correct the expectation the vacuous one had been hiding

## Scope

- `dev/quality/namespace_retirement_sweep.py`
- `dev/tests/test_projection_ref_compiler_callers.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py`

## Changes

- `M` `dev/quality/namespace_retirement_sweep.py`
- `M` `dev/tests/test_projection_ref_compiler_callers.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry_taxonomy_consumer.py`
- `verify:` sweep completes and reports 2 stale pins where it previously crashed
- `verify:` `pytest both repointed gates -n 0 -m ""` -> pass (21)

## Notes

The sweep crashed partway through. It globs the tree and then reads what it
found, and on a shared worktree those are two different moments: a peer deleted
`core/_type_adapters.py` between them.

That failure mode is worse than it looks, which is why the fix is a tolerant
reader rather than a narrower glob. A sweep that dies at file four hundred has
silently not checked files four hundred to nine hundred, and reports nothing
about them -- the same shape as every vacuous gate this campaign has found, in
the tool built to find them.

With it running, it found two gates pinning a module the same peer had made
public.

The storage-taxonomy one was RED, not silent, because it carries its own
`assert declaration.is_file()`. That is the anti-vacuity guard working, and worth
noting as the counter-example: a pin with a presence assertion beside it fails
loudly instead of scanning nothing.

The projection-ref one had no such guard and was scanning with a
`_COMPILER_HOME` that no longer existed. Repointing it made it run for the first
time since that rename, and it immediately reported real drift: the registry
loader's projection-ref compilation had moved into `_loader_internals.py` when
the loader was split, and the expectation still named `loader.py`.

The contract did not change -- that module is still the registry loader, only a
different file of it -- so the expectation was updated rather than the code. What
is worth keeping is that this is the SECOND time this one expectation has gone
stale by a move; its own docstring records the first, about its other path. Both
times the gate went quiet rather than red.
