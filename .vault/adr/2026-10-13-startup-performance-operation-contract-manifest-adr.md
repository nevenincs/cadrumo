---
tags:
  - '#adr'
  - '#startup-performance'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:135dab2258eb9b729269e089989b395cb2fe9f25bc9f8b68c9deed747ed17ca2'
related:
  - "[[2026-10-13-startup-performance-audit]]"
---

# `startup-performance` adr: `Generated operation contract manifest` | (**status:** `accepted`)

Accepted on the owner's first-hand authorization of 2026-10-13: "login should be instantanous", "fix the architecture", "everything must be fixed that is a critical performance degradation".

## Problem Statement

A profile worker now reaches readiness without the operation graph and composes the registry in the background after sign-in. Home and edit admission still need every operation's public contract, and a contract carries schema fingerprints computed from the request, result and projection models. Producing one contract therefore imports its definition and handler, so the first screen after sign-in imported and built every registered operation: about 2,870 modules and 52 s on the loaded host measured on 2026-10-13 (finding `import-bloat-worker` in `2026-10-13-startup-performance-audit`). The runtime and the terminal interface built the same full registry only to read contracts.

## Considerations

- A contract is a pure function of its definition; nothing in it varies per profile or per process (`src/cadrumo/application/operations/_registry_contracts.py`).
- Consumers that need only contracts are the many; consumers that need a definition need exactly one at a time (`src/cadrumo/application/operations/registry.py` lookups by ID).
- A cached artefact can drift from code. Drift must refuse, never execute against an outdated contract.
- Runtime code never imports `dev/`; generated data ships as package data, as the provider-settings catalogue does (`dev/provider_catalog/generate.py`).

## Considered options

- **Background composition only (status quo).** Keeps the sign-in reply fast, but Home waits for every import. Rejected.
- **Cache fingerprints at runtime on disk.** Still imports every model on the first run and adds a mutable cache to trust. Rejected.
- **Generated manifest plus per-group lazy composition (chosen).** Contracts come from data; a definition and its handler import only when that operation is used.

## Constraints

- A dev generator produces `src/cadrumo/_data/operations/contract_manifest.json` from the real eager registry: every operation's definition ID, full public contract (frontend-neutral shape, schema identities and fingerprints, contract digest), its ephemeral-secret lifetime, the composition group that builds it and the module of its handler. The contract-set digest covers the whole set.
- Runtime reads the manifest and composes an operation's group only when that operation's definition, registration or schema binding is needed. A composed group is admitted only when it builds exactly the manifest's operations for that group and every contract equals the manifest's; otherwise the registry refuses.
- CI and the test suite fail when the manifest disagrees with the real definitions, fingerprints included (`just check-operation-contract-manifest` and a test in the owning package).
- The eager registry stays the validation authority: the generator and the drift test compose it and its fixed-point checks.
- Home's read path imports no operation handler module; a deterministic module-graph gate pins this, not a wall-clock budget.

## Implementation

We will split the monolithic production registry builder into named composition groups, one per owning operation module, each importing its own builders inside its function. `build_production_operation_registry` composes every group eagerly; a manifest-backed registry composes them on first use. The worker, the runtime and the terminal interface use the manifest-backed registry. The group table and the shared composition inputs live with the composition seam in `src/cadrumo/entrypoints/`; the manifest model and the lazy registry live in `src/cadrumo/application/operations/contract_manifest.py`.

## Rationale

The manifest removes the only reason contract readers imported handlers, and the admission check keeps the eager definitions authoritative: a stale manifest is a refusal, caught first by the drift gate. Per-group composition keeps the first operation's cost proportional to that operation.

## Consequences

- A change to any operation's contract requires `just generate-operation-contract-manifest`; the drift gate names it.
- A new operation is enrolled in the group table as well as in its owning module.
- Cross-group schema-identity conflicts are detected by the eager build at generation time and incrementally at runtime, not all at once at startup.
- The tax authority, the profile repositories and Home's own read model remain on Home's path; they are separate findings in the audit.
