---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:64580e1a0229e18e7c44fff60b6499bd1e2a8ff09f323f11f1aea7987bb69d86'
step_id: 'S129'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution: `P05.S129`

## Scope

- [ ] `P05.S129` - Refactor the size-budget subjects in secure_objects.py into cohesive siblings without raising any threshold.; `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`.

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`
- `A` `src/cadrumo/adapters/persistence/storage/sql/_secure_object_writes.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/__init__.py`
- `M` `src/cadrumo/adapters/persistence/storage/sql/tests/_secure_objects_support.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/sql/tests` -> `169 passed, 2 warnings in 7.15s; EXIT=0`

## Notes

- Ownership instrument: `uv run --no-sync python -c 'from cadrumo.adapters.persistence.storage import sql; from cadrumo.adapters.persistence.storage.sql import secure_objects; from cadrumo.adapters.persistence.storage.sql._secure_object_writes import SecureObjectWriteOperations; repository = sql.SecureObjectRepository; assert repository is secure_objects.SecureObjectRepository; assert repository.__module__ == "cadrumo.adapters.persistence.storage.sql.secure_objects"; assert repository.__mro__ == (repository, SecureObjectWriteOperations, object); assert repository.save.__module__ == "cadrumo.adapters.persistence.storage.sql._secure_object_writes"; assert repository.apply_batch.__module__ == "cadrumo.adapters.persistence.storage.sql._secure_object_writes"; assert repository.load.__module__ == "cadrumo.adapters.persistence.storage.sql.secure_objects"; print(f"public_owner={repository.__module__}.{repository.__qualname__}"); print("mro=" + " -> ".join(item.__name__ for item in repository.__mro__)); print(f"save_module={repository.save.__module__}"); print(f"apply_batch_module={repository.apply_batch.__module__}"); print(f"load_module={repository.load.__module__}")'` produced `public_owner=cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`; `mro=SecureObjectRepository -> SecureObjectWriteOperations -> object`; `save_module=cadrumo.adapters.persistence.storage.sql._secure_object_writes`; `apply_batch_module=cadrumo.adapters.persistence.storage.sql._secure_object_writes`; `load_module=cadrumo.adapters.persistence.storage.sql.secure_objects`; `EXIT=0`.
- `uv run --no-sync python -m dev.audit.size_budget` exited 1 with 87 remaining whole-tree findings (64 module overages, 22 callable overages, and this target's stale `1617` pin at `1191` lines). `P05.S227` owns the final baseline-only regeneration; no baseline entry was changed here.
