---
tags:
  - '#adr'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-09-11'
body_hash: 'sha256:ff42246a804eab81d4fb49588532183b6d4ae24bfd8e18510647ee47617ca0c7'
related:
  - '[[2026-07-01-import-centralization-research]]'
  - '[[2026-07-02-import-centralization-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-09-11-import-centralization-import-authority-drift-audit]]'
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

## 2026-09-11 amendment: closed lanes, governed tests, and one import verdict

The import-authority drift audit establishes that the canonical-module decision is substantially present in the codebase but is not yet closed or singly enforced. This amendment makes the complete lane model and the contributor-facing verdict explicit. Where an earlier accepted record permits package-facade consumption, application construction of concrete adapters, test-layer carve-outs, warning-only import findings, or an independently authoritative scanner, this amendment controls.

### Source and package classification

`src/` is the product-source boundary. Every Python module below it is governed, including tests, fixtures, `conftest.py`, type-only code, local imports, dynamic imports, and files excluded from distribution artifacts. No module under `src/` may import, dynamically load, or otherwise depend on `dev`, `docs`, `.vault`, `.vaultspec`, root-level test support, or any undeclared first-party root. There is no test exception to this rule.

The closed `cadrumo` lanes are:

- `cadrumo.core`: core.
- `cadrumo.domain`: domain. Public domain-to-domain imports are permitted when they target the canonical public defining module.
- `cadrumo.application`: application and inward-owned application ports.
- `cadrumo.adapters.inbound`, `cadrumo.adapters.outbound`, and `cadrumo.adapters.persistence`: concrete adapter peers.
- `cadrumo.entrypoints` direct modules: shared composition-root code; `cadrumo.entrypoints.cli` and `cadrumo.entrypoints.tui`: sibling outermost entrypoints.
- `cadrumo._data`, `cadrumo.locales`, and generated `cadrumo_data` artifacts: passive resource/data surfaces reached through an inward resource boundary.
- `cadrumo.tests`: neutral core-only test support. Tests below another package inherit that nearest owner's lane.
- `cadrumo.llm`: migration-only; it is merged into `cadrumo.adapters.outbound.llm` and has no independent final-state lane.
- `cadrumo_harness`: a separately shipped outer stub. `cadrumo` never imports it. Until it is retired or explicitly completed, it may consume canonical inward product modules but not `cadrumo.entrypoints` or repository-only roots. Its tests inherit the same restriction.

Any new source root or package without an explicit classification is a gate error.

### Closed dependency direction

Core imports only core and approved passive resource access. Domain imports domain and core. Application imports application, domain, core, and inward-owned ports; it never imports concrete adapters. Each concrete adapter imports its own implementation package plus inward-owned ports/contracts, application, domain, and core, but not a concrete sibling adapter merely for reuse. Entrypoints compose inward packages and concrete adapters. Nothing outside `cadrumo.entrypoints` imports an entrypoint, and CLI, TUI, and any later sibling entrypoint do not import one another. Shared contracts needed by more than one outer package move inward.

Tests do not gain permissions from being tests. A test or fixture has exactly the permissions of its nearest owning package. Cross-layer integration tests live at the outermost seam they exercise. Moving setup into a fixture, `TYPE_CHECKING` block, helper, or dynamic import does not change the edge.

### Complete import-form rule

Every static import under `src/cadrumo` that resolves to another `cadrumo` module uses explicit relative syntax and targets the canonical public defining module. The rule applies at module scope, in class bodies, conditionals, exception handlers, functions and methods, annotations, fixtures, and `TYPE_CHECKING` blocks. Absolute intra-`cadrumo` imports, package-facade symbol imports, re-exports, aliases, forwarding modules, private cross-package reaches, and active package initializers are violations. A child module object may be imported from its parent only when that child module is itself the consumed object and the initializer does not bind or forward it; symbol imports name the defining module.

Literal dynamic targets and statically enumerable target sets obey the same lane, source-boundary, privacy, and canonical-home rules. Intra-`cadrumo` dynamic imports use relative targets anchored to the importing package. A computed target that may resolve first-party must pass through one approved centralized resolver with a closed, provable target set; an unresolved first-party candidate fails. Raw `__import__` is prohibited for first-party loading unless that resolver proves the same contract. Executable embedded Python is parsed or replaced with typed declarations. Process-invocation strings are not imports and do not authorize an in-process sibling-entrypoint dependency.

### Sole enforcement authority

`just check-imports` is the only contributor-facing import-quality verdict. `.importlinter` owns the complete package classification and dependency graph. It is exhaustive over governed roots and includes local and type-only edges. One subordinate parser may run behind the command for relative syntax, canonical defining modules, privacy, inert initializers, forwarding/re-export shapes, and supported dynamic imports that Import Linter cannot express. That parser does not contain a second lane matrix or emit an independent policy verdict.

Every component fails closed. A broken contract, unclassified package, parser failure, unreadable source, missing executable, unresolved first-party dynamic target, unsupported import form, or architectural warning makes `just check-imports` non-zero. Development reports consume that process result; they do not reparse Import Linter grammar or reinterpret an unavailable gate as advisory evidence.

Duplicate pytest predicates and development scanners are removed only after the exact predicate is represented by the authoritative driver and a planted defect demonstrates that the driver fails. Distinct runtime behavior, artifact packaging, third-party dependency declaration, and governance tests remain. The planted-defect suite covers every lane direction and syntax/dynamic family through `just check-imports` itself.

### Migration discipline

No current violation is grandfathered. No count becomes a baseline, no wildcard test carve-out survives, no warning is accepted as an architectural result, and no broad `ignore_imports` entry remains. Migration proceeds from source-boundary leaks through inward-layer inversions, application-to-adapter edges, adapter-sibling coupling, entrypoint crossings, test relocation and support splitting, the LLM merge and harness disposition, then canonical static and dynamic import cleanup. The gate may remain red on an implementation branch while the violations are removed; it becomes the repository verdict only with zero violations and proven teeth.
