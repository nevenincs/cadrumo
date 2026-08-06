---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
body_hash: 'sha256:74fbf5ab0be02fd0aec01789d10a2cfd1c2be5db26a5c8e8a72dd9fab6f30960'
step_id: 'S13'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Rename the schema-provider role-family (RegistrySchemaProvider / CasillaSchemaProvider) to a name that says schema source / accessor distinct from the settled resolver port, as one atomic relocation:RegistrySchemaProvider commit, sweeping the class def, builder returns, __all__, and the ~6 consumer sites in filing runtime

## Scope

- `regen docs-scaffold + API-stub + docstring-core-struct in the same commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/filing/runtime.py`

## Description

- Rename the concrete frozen-dataclass schema accessor `RegistrySchemaProvider` to `RegistrySchemaAccessor`, so its name says it accesses registry schema (collections and modelo subviews from validated TOML), distinct from the settled resolver port.
- Sweep `runtime.py` (def, the builder return annotations, the constructor call, `__all__`, docstrings) and its three consumer files (`_export.py`, the export and import test modules).
- Keep the `build_runtime_schema_provider` builder verb name.
- Leave the domain `CasillaSchemaProvider` protocol it structurally satisfies untouched.

## Outcome

Landed as one atomic commit `relocation:RegistrySchemaProvider` (`5d04ea912`). collect-only clean, ruff clean, the 230 filing tests green. The domain protocol and the settled resolver contract are not renamed.

## Notes

Anchor HEAD-shape deviation from the reference: the reference estimated the schema-provider family at roughly six sites, but the family is actually two distinct types: the concrete `RegistrySchemaProvider` (the four-file filing-runtime consumer set this Step renames, matching the six-site estimate) and the domain `CasillaSchemaProvider` protocol (roughly forty cross-layer consumers across domain, application filing, and workflow). The plan scopes S13 to `filing/runtime.py`, so this Step renames only the concrete `RegistrySchemaProvider`; the domain protocol rename is out of scope (a domain-layer protocol rename of that breadth is not a filing-runtime change). Recorded for the coordinator. All four scoped files were clean of peer WIP.
