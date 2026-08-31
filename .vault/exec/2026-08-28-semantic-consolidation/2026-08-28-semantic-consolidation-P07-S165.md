---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d7dde64598446c5a681d69b1175b614719f72b1e48fbd95c8a7ed503221d291e'
step_id: 'S165'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Relocate the topics catalogue and the AEAT access gate onto public modules, moving the pinned public surface and the error-registry entries with them

## Scope

- `src/cadrumo/core/`

## Changes

- `A` `src/cadrumo/core/topics/catalogue.py`
- `A` `src/cadrumo/core/access_gate/gate.py`
- `M` `src/cadrumo/core/errors/registry/_application_part1.py`
- `M` `src/cadrumo/core/topics/tests/test_catalogue.py`
- `M` both namespaces inert; 31 consumers repointed
- `verify:` `pytest core/topics -n 0 -m ""` -> 8 passed
- `verify:` `--collect-only` -> 28925 collected, 6 errors, all pre-existing and peer-owned

## Notes

Both namespaces named their new home PUBLICLY -- `catalogue.py`, `gate.py` --
because every consumer sits outside the package. A relocation onto an
underscore-private module would have converted a namespace import into a
cross-package private import, trading one rule violation for another.

That is a correction to the two relocations recorded under S164, which landed on
`_service.py` and whose consumers are in other packages. Renaming those requires
removing a file, which the operator's standing prohibition on destructive
commands forbids, so it is flagged rather than done.

### Two couplings the relocation had to carry with it

Neither is visible from the moved code.

The error-code registry keys exceptions by fully-qualified module path, so
`cadrumo.core.topics.TopicNotFoundError` became
`cadrumo.core.topics.catalogue.TopicNotFoundError` and its registry entry had to
move in the same change. The registry refuses at import time on an unregistered
subclass, so this surfaced immediately rather than silently -- the gate did its
job.

And a surface gate pinned `topics.__all__` against an expected set, asserting
that CLI and rendering symbols never leak into the topics package. Emptying the
namespace made that assertion vacuously comparable to an empty set and it failed
loudly, which is the correct behaviour for a gate whose subject moved. The
`__all__` moved onto `catalogue.py` and the gate now reads it there, so the
intent -- topics are backend catalogue records -- is preserved rather than
weakened to fit the new shape.

The general lesson is that a namespace's public surface can be load-bearing for
something other than imports. Retiring it is not always a no-op even when every
consumer is repointed correctly.
