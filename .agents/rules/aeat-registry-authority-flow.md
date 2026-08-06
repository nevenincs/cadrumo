---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority flow

Treat the modelo registry as a deterministic authoring-compiler pipeline:

`TOML authoring tree -> loader/compiler -> strict schema objects -> registry validation -> validated authority -> immutable snapshots -> runtime projections`.

Keep `ValidatedRegistryAuthority` as the production orchestration boundary for registry-backed modelo access. Request validated modelos, deadline windows, and snapshots through the authority or a repository facade that owns an authority. Do not add new production paths that call raw loaders and then independently validate or select revisions.

Keep `_loader.py` as the TOML compiler implementation detail. Loader changes MUST preserve deterministic merge order, reject ambiguous scalar conflicts, include every read TOML file in cache invalidation, and compile fragments into the existing strict `ModeloDefinition` / `ModeloRevision` runtime schema.

Keep snapshot construction authority-owned. Runtime consumers such as filing schema providers, query services, formula execution, export parsing, and adapter projections MUST consume `RegistrySnapshot` or typed projections derived from snapshots, not fragment paths or partially merged raw dictionaries.

Invalidate any cache above the loader by the complete registry tree fingerprint, including directory-mode manifests and recursive revision fragments. Do not introduce path-only registry caches that can serve stale TOML after source edits.