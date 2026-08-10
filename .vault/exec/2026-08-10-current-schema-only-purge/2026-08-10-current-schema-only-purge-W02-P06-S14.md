---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9728e9ece5d440bc1933aa2051d726caea864fbf5800f61fd453638c2c2e0331'
step_id: 'S14'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require and explicitly write the exact current SecretIndex marker

## Scope

- `src/cadrumo/adapters/persistence/storage/secret_store/_secret_store.py`

## Description

- Drop the default from the secret-store index version field so the marker is
  required.
- Stamp the version explicitly on the fresh index materialised when no index file
  exists.
- Record in the field docstring why the default was the defect and what the one
  legitimate source of an unstamped index is.

## Outcome

Landed in `005816f` with its proof step.

The equality gate already existed and already refused a non-current index. The
default made it blind to the case it most needed: an index file omitting the key
hydrated AS current, so the gate read a value the writer never wrote and passed.
The consequence here is worse than a bad read, because every mutation rewrites
the whole index -- the misread value would then be written back over the file it
misread, converting a silent misinterpretation into a persisted one.

The interesting line is the absent-file branch. When no index exists the store
materialises a fresh empty one, which is create-on-first-access and is
forward-functional: an absent file is a store that has never been written, not a
document to interpret. Making the field required could have been satisfied by
leaving the default in place, which would have preserved the defect exactly.
Instead the fresh instance is stamped at that one site, so the single legitimate
source of an unstamped index is explicit at the point it occurs, while a FILE
that omits the marker still refuses.

That is the distinction the governing compatibility decision draws between fresh
schema creation and legacy read-tolerance, applied at the one line where the two
look identical.

## Notes

No write-path change was needed for mutations: they carry the version forward
from the loaded instance, which is now guaranteed to have been either read from a
stamped file or stamped at creation.
