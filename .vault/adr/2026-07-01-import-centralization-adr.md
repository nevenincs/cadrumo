---
tags:
  - '#adr'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-08-25'
body_hash: 'sha256:57410a053ffb2e6cb446019a664078392400f8212d05779e457758c7910dc5c5'
related:
  - '[[2026-07-01-import-centralization-research]]'
  - '[[2026-07-02-import-centralization-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
---
# `import-centralization` adr: `canonical defining modules as the sole cross-package import surface` | (**status:** `accepted`)

## Problem Statement

The original facade-centralization campaign reduced private cross-package reaches but replaced them with package namespaces that aggregate unrelated contracts, obscure canonical ownership, create import cycles, and permit the same symbol to appear at multiple import paths. The reproducible census and migration history remain grounded in `2026-07-01-import-centralization-research` and `2026-07-02-import-centralization-audit`.

This amendment replaces facade promotion with direct defining-module ownership. It preserves the accepted hexagonal dependency direction and atomic-relocation discipline while eliminating package facades, re-export bridges, aliases, and compatibility paths.

## Decision

1. Every cross-package public symbol has one definition in one semantically named, non-underscore module. Every consumer imports that symbol directly from its defining module.
2. Package namespaces are structural and inert. A package `__init__.py` imports, binds, aliases, lazily resolves, or re-exports no project symbol. An empty `__all__` may document the inert boundary.
3. A cross-package reach into an underscore-private module triggers one of two outcomes: remove the reach as a design defect, or hard-move the shared contract and its tests to a public defining module. Promotion through `__init__.py` is prohibited.
4. The previously named bridge exceptions are revoked. A public module is legitimate only when it defines its owned implementation or contract; a forwarding module is not a canonical home. `__main__.py` may dispatch an executable but never exports a project symbol.
5. Hierarchical roll-ups, umbrella exports, redundant application/domain exports, package aliases, forwarding wrappers, and multi-sourced public symbols are retired. Canonical ownership is the defining module, not a package-level import path.
6. Dynamic imports target the exact canonical defining module. String-built module paths obey the same rule as static imports.
7. Production, tests, fixtures, development tools, annotations, `TYPE_CHECKING` imports, registrations, plugin targets, and local imports obey the same rule immediately.
8. The import-hygiene gate resolves definitions and rejects package imports used for symbols, re-exports, aliases, forwarding wrappers, private cross-package reaches, multi-sourced symbols, dangling imports, and orphaned bridge modules. It inventories canonical defining modules and symbols rather than package export sets.
9. Every relocation is atomic: move the definition and its owning tests, update every production/test/tooling consumer and dynamic target, update manifests and receipts, delete the former module and every export surface, and prove clean collection in one explicit-path commit. No temporary alias, shim, fallback, or re-export may bridge the move.

## Constraints

- Intra-package underscore-private modules remain valid only when their symbols never cross the package boundary.
- Public module names describe the owned contract or capability; mechanically stripping an underscore without adjudicating ownership is prohibited.
- Moving an import path must not duplicate policy, storage, mutation, lifecycle, or rendering authority.
- The accepted layer direction remains unchanged. Direct defining-module imports do not authorize a lower layer to import a higher layer.
- Current-only pre-release cutovers delete old readers, fixtures, and compatibility paths rather than translating them.
- Registry dispatch modules may own real dispatch definitions but may not re-export per-family symbols.

## Implementation

The existing import-hygiene scanner and its tests are amended in place to model package namespaces as inert and public defining modules as the only legal cross-package targets. Existing package `__init__.py` export populations are migrated in bounded atomic slices, prioritizing contracts that already create facade cycles or hide rejected authorities.

For each symbol, the migration census records its current definition, every import form, canonical defining module, consumer class, dynamic target, manifest or receipt reference, and deletion proof. The gate reaches fixed point only when package binding inventories are empty and every public symbol resolves to one definition and one direct import path.

## Rationale

A package facade is an additional import authority even when it does not duplicate implementation. It hides the module that owns the contract, couples unrelated consumers to package initialization, and permits re-export graphs that make deletion and cycle analysis indirect. Direct defining-module imports preserve one canonical home, make dependency edges explicit, and satisfy the no-shim/no-redeclaration architecture established by `2026-07-02-arch-remediation-program-adr`.

## Consequences

- Cross-package dependencies become exact and mechanically auditable.
- Package initialization becomes effect-free and cycle-resistant.
- Existing facade consumers require broad atomic migration, including tests, manifests, receipts, and dynamic imports.
- Some underscore-private modules must become public defining modules; rejected or single-caller callback authorities are deleted instead.
- Import statements are more explicit, but ownership and deletion proofs no longer depend on tracing umbrella exports.
