---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:474bfdc75d13fea78ccc1ed2e1b88f7898db1cd3f1e7181561809484a48222ac'
related:
  - "[[2026-07-01-import-centralization-research]]"
  - "[[2026-07-01-import-centralization-adr]]"
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
  - "[[2026-07-08-importlinter-test-carveout-adr]]"
  - "[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]"
  - "[[2026-07-01-import-centralization-plan]]"
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---
# `import-centralization` audit: `Import authority drift and single-gate ownership`

## Scope

This audit verifies the live `src/` import topology and every overlapping import-policy mechanism against the accepted canonical-defining-module and hexagonal-boundary decisions. It covers authored Python under `src/cadrumo` and `src/cadrumo_harness`, generated or packaged data namespaces, colocated tests and fixtures, `.importlinter`, `just check-imports`, development scanners, pytest architecture tests, packaging declarations, and the development health report. It records current drift and the complete target model approved on 2026-09-11; it changes no product code or gate configuration.

The repository is substantially aligned in intent. The live `just check-imports` command passes and direct Import Linter execution reports 13 kept contracts and zero broken contracts. That green result is not yet sufficient evidence for the requested policy: the analyzed roots and import forms are incomplete, layered coverage is not exhaustive, type-checking imports are excluded, and the current ignore ledger contains at least 3,110 matched or declared paths across the measured broad entries. A static census also found 72 absolute intra-`cadrumo` imports, 266 `test_support` import sites from `src/cadrumo`, 64 literal first-party dynamic targets, 50 computed dynamic candidates, and active package initializers that require canonical-home adjudication.

## Findings

### accepted-record-conflict | critical | Two accepted decisions still authorize behavior the canonical import decision forbids

The ports-inversion ADR requires consumers to use package top-level re-exports, while the later amendment to the import-centralization ADR makes package namespaces inert and requires direct defining-module imports. The accepted import-linter test-carveout ADR explicitly permits test and fixture imports to cross forbidden layers through broad wildcard ignores, while the approved target makes tests inherit their owner lane without exemption. Contributors cannot satisfy all three records simultaneously.

### graph-green-with-hidden-edges | critical | The current green graph omits governed roots and import forms

`.importlinter` analyzes `cadrumo` and `dev`, excludes type-checking imports, leaves the main layered contract non-exhaustive, and does not classify `cadrumo_harness`, generated companion data, or root-level support as closed lanes. Function-local imports are represented only when the graph builder recognizes them; dynamic targets and canonical syntax require separate parsing. A passing result therefore does not yet prove the closed model.

### source-boundary-leakage | high | `src/` can still know repository-only support

The product-source boundary is not expressed as a closed root rule. Imports from `src/cadrumo` into `test_support` are widespread, and current contracts do not uniformly forbid `dev`, `docs`, `.vault`, `.vaultspec`, root test support, or an undeclared first-party root. The approved boundary is stricter: no authored or colocated-test module under `src/` may import repository-only surfaces, including type-only, deferred, or dynamic forms.

### incomplete-lane-classification | high | Several shipped and test-support namespaces lack an unambiguous lane

The current architecture names core, domain, application, adapters, and entrypoints, but does not completely classify resource packages, shared tests, `cadrumo.llm`, or `cadrumo_harness`. The approved disposition is to merge `cadrumo.llm` into `cadrumo.adapters.outbound.llm`; treat `cadrumo_harness` as a separately shipped outer stub that must either be retired or completed without becoming a product dependency; and classify every test by its nearest owner rather than by the word `test` in its path.

### syntax-and-canonical-home-gap | high | Graph contracts cannot enforce the complete canonical import form

Import Linter is the correct dependency-graph authority, but it cannot alone reject absolute intra-package spelling, facade consumption, forwarding modules, private cross-package reaches, unresolved computed dynamic targets, or package initializer bindings. Existing AST tests and scanners cover fragments of this space with overlapping predicates and inconsistent scopes.

### duplicate-policy-authorities | high | Pytest gates and scanners independently restate import rules

The overlapping set includes the core-boundary, relative-import resolution, cross-module resolution, test-support import, inert-namespace, lazy-facade, namespace-attribute, dunder/private, test-alias, TUI AST-import, harness-direction, and registry-public-API tests, plus `dev/import_hygiene_scan.py` and related quality scanners. Their import-policy portions overlap `.importlinter` and one another. Tests that also protect runtime behavior must be split so only the distinct behavior assertion survives.

### nonblocking-consumer-interpretation | high | The development health report can disagree with the blocking gate

`dev/audit/report.py` reruns Import Linter, parses its textual contract grammar, counts declarations independently, and may report tool unavailability as AMBER in its nonblocking workflow. That creates a second interpretation of import health. The product-quality audit already recommends consuming process success or failure instead of reconstructing the contract verdict.

### distribution-boundary-ambiguity | medium | Excluding tests from artifacts does not remove them from architecture

The build configuration separately includes the main and harness source roots and excludes many test paths from artifacts. Colocated `conftest.py` and other support shapes are not uniformly described. Artifact exclusion is a packaging property only; every authored module under `src/`, including excluded tests and fixtures, remains subject to source-boundary and lane rules.

## Complete package and lane classification

The classification is closed: any new first-party package or source root that lacks a row is an error.

| Package or namespace | Lane | Permitted role |
| --- | --- | --- |
| `cadrumo.core` | core | Innermost product primitives and inward resource access contracts. |
| `cadrumo.domain` and all public domain-owned subpackages | domain | Domain policy. Public domain-to-domain imports are legal when they use relative syntax and the canonical public defining module. |
| `cadrumo.application` | application | Use cases, orchestration, and application-owned ports or contracts. |
| `cadrumo.adapters.inbound` | inbound adapter | Converts external input toward application or domain contracts. |
| `cadrumo.adapters.outbound` | outbound adapter | Implements outward services against inward-owned contracts. |
| `cadrumo.adapters.persistence` | persistence adapter | Implements persistence ports; it is a concrete adapter peer, not an inward service. |
| `cadrumo.llm` | migration-only outbound adapter | Merge into `cadrumo.adapters.outbound.llm`; the top-level package has no independent final-state lane. |
| direct modules in `cadrumo.entrypoints` | shared composition root | Shared launcher-only composition that does not make sibling entrypoints depend on one another. |
| `cadrumo.entrypoints.cli` | CLI entrypoint | Outermost CLI composition root. |
| `cadrumo.entrypoints.tui` | TUI entrypoint | Outermost TUI composition root. |
| `cadrumo._data`, `cadrumo.locales`, and generated `cadrumo_data` artifacts | resource/data | Passive shipped resources reached through an inward resource boundary; they do not import product layers. |
| `cadrumo.tests` | neutral shared test support | Core-only helpers. Any helper needing an outer layer moves to that layer's test seam. |
| tests or `conftest.py` below a product package | inherited owner lane | Same permissions as the nearest owning package, with no fixture exemption. |
| `cadrumo.adapters.tests` | adapter integration-test seam | May compose concrete adapters and inward contracts, but cannot authorize inward production dependencies. |
| `cadrumo.entrypoints.tests` | shared-entrypoint test seam | Tests only shared entrypoint composition; CLI- or TUI-specific tests belong under that sibling. |
| `cadrumo_harness` and `cadrumo_harness.mcp` | separately shipped outer stub | Must not be imported by `cadrumo`; may consume canonical inward product modules but not `cadrumo.entrypoints` siblings. It must be retired or explicitly completed as its own composition root. |
| `cadrumo_harness._data` | harness resource/data | Passive resources owned by the harness stub. |
| `cadrumo_harness.tests` and nested MCP tests | inherited harness lane | Same restrictions as the harness stub. |
| `dev`, `docs`, `.vault`, `.vaultspec`, root `test_support`, and any undeclared first-party root | repository-only or unclassified | Forbidden targets from every module under `src/`; an undeclared first-party root fails the gate. |

## Allowed dependency matrix

An entry means a direct import is structurally allowed; canonical-module, privacy, and syntax rules still apply.

| Importer | Allowed first-party targets |
| --- | --- |
| resource/data | itself and same resource namespace only |
| core | core and approved passive resource/data access |
| domain | domain and core |
| application | application, domain, core, and application-owned ports |
| inbound adapter | its own adapter package, application-owned ports/contracts, application, domain, and core |
| outbound adapter | its own adapter package, application-owned ports/contracts, application, domain, and core |
| persistence adapter | its own adapter package, application-owned ports/contracts, application, domain, and core |
| shared entrypoint modules | inward packages and concrete adapters solely for composition |
| CLI entrypoint | inward packages and concrete adapters; never TUI or another sibling entrypoint |
| TUI entrypoint | inward packages and concrete adapters; never CLI or another sibling entrypoint |
| harness stub | canonical inward packages only; never `cadrumo.entrypoints`, `dev`, or another repository-only root |
| neutral shared test support | core and passive test data only |
| owner-colocated test | exactly its owning lane's row |
| outer integration test | the row of the outermost seam it exercises |

Nothing outside `cadrumo.entrypoints` imports an entrypoint. Application and domain never import concrete adapter implementations. Concrete adapter siblings do not couple to one another merely for reuse; shared contracts move inward. `src/cadrumo` never imports `cadrumo_harness`.

## Exact import scope

- Every static `import` and `from` statement anywhere under `src/cadrumo`, including module scope, class bodies, conditionals, exception handlers, functions, methods, fixtures, and `if TYPE_CHECKING`, participates in the same graph and source-boundary policy.
- Every import from one `cadrumo` module to another uses explicit relative syntax. Absolute `cadrumo...` spelling is an error. A separate top-level distribution such as `cadrumo_harness` uses the canonical absolute product path when consuming `cadrumo`; relative syntax cannot cross distribution roots.
- Consumers import symbols from the public module that defines them. Package-facade imports, `__init__` bindings, re-exports, aliases, forwarding modules, and private cross-package imports are errors. For `cadrumo.domain.foo._implementation`, the private owner is `cadrumo.domain.foo` and its descendants only.
- Public domain-to-domain imports are allowed under the domain matrix row. Public means a canonical non-underscore defining module, not a package facade.
- `from ..core import config` is allowed only when `config` is itself the directly consumed child-module object and the package initializer does not bind or forward it. Symbol consumption uses `from ..core.config import Symbol`.
- Package initializers are inert. `__main__.py` may import and dispatch its own executable but may not expose a forwarding API.
- Literal dynamic targets and statically enumerable target sets are resolved and checked against the same lane, source-boundary, privacy, and canonical-home rules. An intra-`cadrumo` dynamic import uses a relative target anchored by the importing package.
- A computed dynamic target that may name a first-party module must be resolved by an approved centralized resolver with a closed target set. An unresolved first-party candidate is an error. Raw `__import__` for first-party loading is prohibited unless that resolver proves the same rules.
- Embedded Python import snippets that execute as Python are parsed or replaced by typed declarations. Process invocation strings, including one entrypoint launching another process, are not imports, but may not be used to create an in-process sibling dependency.
- Parser failures, unreadable files, missing source roots, and unsupported import forms are gate errors rather than skipped findings.

## Overlapping enforcement inventory

| Mechanism | Current overlap | Final disposition |
| --- | --- | --- |
| `.importlinter` | Dependency direction, roots, test ignores, and layered graph | Sole declarative owner of package classification and allowed dependency directions; make roots and layers exhaustive and remove broad ignores. |
| `just check-imports` | Currently invokes one quiet lint wrapper | Sole contributor-facing verdict and orchestrator for every import check. |
| `dev/import_hygiene_scan.py` and related AST scanners | Private imports, facades, forwarding modules, syntax, partial dynamic targets | Replace or narrow into one subordinate syntax/canonical/dynamic checker with no lane matrix or independent verdict. |
| architecture pytest tests | Re-state source, layer, relative, private, facade, harness, entrypoint, or registry import predicates | Remove only after equivalent planted-defect proof passes through `just check-imports`; split and retain distinct runtime behavior. |
| `dev/audit/report.py` layering dimension | Re-runs and parses Import Linter output | Consume the authoritative command result only; non-zero is RED, zero is GREEN, and unavailable execution cannot become an advisory substitute for the blocking gate. |
| packaging tests | Distribution inclusion and exclusion | Retain as distinct artifact-behavior tests; do not treat excluded tests as architecture-exempt. |
| dependency declaration tests | Third-party declaration completeness | Retain; this is not first-party import direction. |
| planted-defect fixtures | Prove a contract bites | Retain and expand as tests of the authoritative driver, not as a second live-tree policy implementation. |

## Single-gate ownership model

`just check-imports` is the sole import-quality verdict. It runs, in order: a fail-closed source-root and lane-classification preflight; Import Linter over the complete graph; and one subordinate parser for syntax, canonical defining modules, privacy, inert initializers, and supported dynamic targets. `.importlinter` owns the lane matrix and no Python scanner may restate it. The subordinate parser owns only properties the graph engine cannot express and reports errors through the same command. Any component abort, warning-class architectural finding, unresolved target, or unavailable executable makes the command non-zero.

The representative defect suite invokes this exact driver against isolated planted violations for every contract family: source-to-`dev`, core-to-outer, domain-to-adapter, application-to-concrete-adapter, adapter-sibling coupling, entrypoint import and sibling-entrypoint import, test-owner crossing, absolute intra-package syntax, facade/re-export/private reach, and literal plus computed dynamic targets. A contract is not accepted until its planted violation makes `just check-imports` fail.

## Migration strategy

1. Amend the accepted records so canonical defining modules, inherited test lanes, strict `src/` versus repository-only separation, and sole-gate ownership are not contradicted by older clauses.
2. Declare every source root and package lane, including shared tests, resources, generated data, and the harness stub. Make an unclassified addition fail before graph evaluation.
3. Put the complete lane matrix in `.importlinter`, include type-only and local imports, make layering exhaustive, and establish planted defects before deleting any old assertion.
4. Close product-source leaks first: remove all `src` imports of `dev`, root support, and other repository-only roots; move genuinely shared support into an appropriate inward product or owner-test module.
5. Burn down current graph exceptions in dependency order: core/domain inversions, application-to-concrete-adapter edges, adapter-sibling coupling, entrypoint crossings, and test-only crossings. No exception becomes a baseline.
6. Merge `cadrumo.llm` into `cadrumo.adapters.outbound.llm`. Decide the `cadrumo_harness` stub explicitly: retire it or complete it as an independent outer composition root without importing product entrypoints.
7. Relocate cross-layer integration tests to the outermost seam and split neutral test support so each helper has one legal owner.
8. Remove absolute intra-`cadrumo` spelling, package facades, re-exports, forwarding modules, private cross-package reaches, and noncanonical dynamic targets; centralize any genuinely computed first-party resolver.
9. Retire duplicate pytest predicates and development scans one predicate at a time only after the authoritative driver has an equivalent planted-defect proof. Preserve distinct behavior, packaging, dependency-declaration, and governance tests.
10. Simplify health reporting to consume the authoritative result, then prove the final tree with `just check-imports`: no warnings, ignores, grandfathered violations, unclassified packages, unresolved imports, or alternate import-quality verdicts.

## Recommendations

Amend the import-centralization ADR as the semantic authority for classification, canonical import form, dynamic-import scope, inherited test permissions, the LLM merge, and the harness disposition requirement. Amend the ports-inversion ADR to replace facade imports with canonical defining modules and inward-owned construction ports. Amend the test-carveout ADR in place to retire its wildcard exemption model and bind tests to owner lanes. Amend the product-boundary ADR so the subordinate analyzer is explicitly a servant of product import authority rather than an independent development model.

Append a new implementation Wave to the import-centralization plan for classification, graph closure, exception elimination, LLM consolidation, harness disposition, test relocation, and canonical-import cleanup. Append a separate Wave to the quality-gate-zero-closure plan for sole-command orchestration, fail-closed behavior, planted-defect proofs, overlap retirement, and report-consumer simplification. The import plan owns policy implementation and migration; the quality plan owns consolidation of how the verdict is delivered. Neither plan may redefine the other's authority.
