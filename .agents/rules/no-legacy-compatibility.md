---
name: no-legacy-compatibility
trigger: always_on
---

# No unowned legacy compatibility

- Before the project declares a released public compatibility floor, remove displaced commands, imports, schemas, configuration keys, aliases, facades, wrappers, and data shapes in the same change that replaces them.
- A passing old caller or test is not by itself a reason to preserve a legacy surface. Update repository consumers to the canonical contract and delete the old path.
- After a public compatibility floor exists, compatibility requires an explicit owner, supported-version window, migration or upgrader path, deprecation signal, and removal condition. Keep it at the boundary; do not duplicate domain implementations.
- Persistent data migrations are forward, deterministic, idempotent, and tested from every supported stored version. Silent coercion or fallback from an unknown shape is forbidden.
- Do not create a shim merely to stage an internal relocation. Canonical definitions and all consumers move atomically under `aeat-architecture-boundaries`.
