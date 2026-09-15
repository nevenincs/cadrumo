---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

## Placement and dependency direction

- Put product Python code under its owning `src/` package and development-only registry compilation, authoring and migration tooling under `dev/registry/`. Runtime must not import the development compiler. Do not create parallel implementations or ad-hoc import roots.
- Preserve the accepted dependency direction: domain code is independent of adapters; application services coordinate domain behavior; inbound, outbound, persistence, entrypoint, and core responsibilities remain separate.
- Put every Python test below the narrowest owning `tests/` directory, never beside implementation modules as a naked `test_*.py`.
- Keep the CLI root surface to `config` and `app`; extend the established hierarchy instead of adding a third root family.

## Canonical definitions and imports

- Every public symbol has one canonical definition in a semantically named, non-underscore module.
- Consumers import directly from that defining module. This applies to production code, tests, development tooling, plugins, dynamic imports, and type-only imports.
- Package `__init__.py` files are inert namespace markers. Do not add exports, lazy maps, `__getattr__`, import forwarding, initialization side effects, or compatibility surfaces.
- Do not create facade modules, re-export layers, alias modules, forwarding wrappers, duplicate definitions, or cross-package imports from private underscore modules.
- Registry domain declarations and runtime resolvers belong to their public defining domain modules; source compilation and corpus validation belong to the development compiler. Enroll each implementation at its owning dispatch boundary without moving development dependencies into runtime.

## Changes

- Relocate a symbol atomically: create the canonical definition, update every consumer and dynamic reference, delete the old definition or forwarding path, then run import-boundary and owning tests.
- Do not keep a transitional shim unless a released public compatibility floor explicitly requires it under `no-legacy-compatibility`.
- Production code, tests, configuration, and user documentation must stand on their own. Do not embed Vaultspec paths, rule slugs, plan or audit identifiers, step numbers, agent roles, or campaign state in them.

Authority: accepted import-centralization architecture decision and the current package-boundary tests.
