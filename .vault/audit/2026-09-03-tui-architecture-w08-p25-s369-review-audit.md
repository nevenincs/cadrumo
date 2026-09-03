---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:747abbcf17c8977d042197294a854c0ca87c9ecfa54472adad5ec5dac4cfde88'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `w08 p25 s369 review`

## Scope

Independent review of `W08.P25.S369` in `src/cadrumo/entrypoints/tui/navigation.py` and its focused tests against the exact plan row, accepted navigation join, and architecture, naming, localization, quality-gate and sensitive-data rules. The review adversarially covered the closed destination vocabulary, descriptor integrity, admission truth, screen-factory protocol, semantic focus identity, uniqueness, search action/destination joins, localization ownership, I/O and dependency direction.

The static catalogue names exactly Home, Ledger, Declarations and AEAT Sync as primary workspaces and Profile as an account destination, using stable locale keys rather than display prose. The builder requires complete admissions, keeps non-available routes factory- and action-free, detects admission drift from search results, joins search actions to the result's admitted destination, and restores search focus by semantic kind plus stable result identity. The module imports only the S368 application contract and Textual screen abstraction in the accepted dependency direction, and inspection found no repository, filesystem, network, localization-catalogue or concrete-screen dependency. Translation population is correctly deferred to S385.

## Findings

### action-authority-bypass | high | Direct navigation targets can send undeclared action candidates to screen factories

`target_for_search_result()` correctly resolves a search candidate through the destination route, but `create_screen()` does not perform the same join. `TuiNavigationTargetV1` is public and accepts any namespaced `action_candidate_id`; `create_screen()` checks only destination availability before copying that value into `TuiScreenContextV1` and invoking the factory. A direct probe constructed a Declarations target carrying `operator.undeclared.execute`; the catalogue accepted it and the factory received that exact undeclared action even though the route declared only `operator.declaration.open`. This creates two authority paths: search results fail closed, while direct command-palette or caller targets bypass the catalogue. The owning screen must never receive an action candidate until the current route has resolved it.

### descriptor-integrity | medium | The public catalogue constructor accepts relabelled and rezoned canonical destinations

`TuiDestinationCatalogueV1` checks only destination-ID coverage and uniqueness. It does not require each route descriptor to equal the canonical descriptor in `TUI_DESTINATION_CATALOGUE`, nor preserve canonical order. A direct probe supplied all five IDs but described `workbench.home` with the Profile label key and `account` zone; construction succeeded and resolution returned the spoofed metadata. The normal builder uses the canonical tuple, but the public exported constructor permits a second catalogue authority that can contradict the accepted user vocabulary and account-placement contract.

### factory-runtime-contract | medium | Invalid factories pass route construction and escape as uncontrolled call errors

`TuiScreenFactoryV1` is runtime-checkable and `create_screen()` validates the returned object, but route construction validates only presence versus absence. A non-callable value cast through the typed boundary was accepted for an available route; screen creation then leaked raw `TypeError: 'int' object is not callable` instead of the declared `DestinationFactoryError`. A callable with an incompatible signature has the same uncontrolled failure shape. The runtime boundary should reject non-conforming factories at catalogue assembly and translate invocation contract failures without masking exceptions raised by a valid factory body.

### navigation-gate-teeth | medium | Focused tests exercise only canonical builder and search-target paths

The 13 focused tests cover the static destination set, admission states, missing factories, unavailable routes, valid factory output, semantic focus, search admission drift, unknown search actions and one import inventory. They do not inject an undeclared action through a directly constructed target, construct a complete catalogue with corrupted descriptor metadata or order, or supply a non-callable/wrong-signature factory. The no-I/O detector reads the production file using test-side `Path`, scans only `ImportFrom` nodes, and does not inspect calls, so it would miss a direct `import pathlib`, aliased I/O, or repository call. Current purity is sound by inspection, but the gate does not prove it.

### final-action-authority | low | Direct targets now use the same fail-closed action join as search results

`create_screen()` now resolves every non-null target candidate through the current route before constructing a factory context. The original direct probe now raises `UnresolvedActionCandidateError`, and the factory is not invoked. The focused regression test exercises this public direct-target path. `action-authority-bypass` is closed.

### final-descriptor-factory-contracts | low | Canonical descriptors and runtime factory shape now fail closed

Route construction now requires its descriptor to equal the static canonical descriptor; catalogue construction additionally requires canonical order. The original relabelled and rezoned Home probe now raises `NavigationContractError`. Available routes validate callable factory shape and one-positional-context binding during assembly, and invalid invocation/return boundaries use `DestinationFactoryError`; the original non-callable probe now fails during route construction. Focused tests cover spoofed metadata, reordered routes, wrong arity and typed invocation failure. `descriptor-integrity` and `factory-runtime-contract` are closed.

### final-gate-disposition | low | Remediation tests detect all reproduced contract defects

The focused suite grew from 13 to 16 tests and now contains direct defect probes for each reproduced authority, descriptor and factory failure. The import-only purity assertion remains narrower than a comprehensive AST I/O detector, but the reviewed module is pure by full inspection, imports in the accepted entrypoint-to-application direction, and carries no repository, network, filesystem, locale catalogue or concrete-screen dependency. That residual test-hardening opportunity does not leave a production defect in S369. `navigation-gate-teeth` is closed for the blocking findings.

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### w08 p25 s369 review | {level} | {summary}

     followed by a paragraph carrying the detail. w08 p25 s369 review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

1. Make `create_screen()` resolve every non-null target action through the current route immediately before context construction, so search, command-palette and direct target paths share one fail-closed authority join.
2. Make the runtime catalogue accept only exact canonical descriptors in canonical order, or make direct construction private and expose only the validated builder.
3. Validate the factory callable/protocol at route assembly and return `DestinationFactoryError` for boundary-shape failures; retain the existing concrete `Screen` return validation.
4. Add bite probes for direct-target undeclared and cross-destination actions, relabelled/rezoned/reordered descriptors, and non-callable/wrong-signature factories. Expand the purity gate across `Import`, `ImportFrom` and relevant call forms.
5. Focused Pytest passed 13 tests; Ruff and ty passed; Basedpyright reported 0 errors, warnings or notes. No critical finding exists, but one high and three medium findings remain open. `W08.P25.S369` must not close.
6. Final remediation probes rejected the undeclared direct action, spoofed descriptor and non-callable factory at their owning boundaries. Focused Pytest passed 16 tests; Ruff and ty passed; Basedpyright reported 0 errors, warnings or notes.
7. No critical, high or medium finding remains open. `W08.P25.S369` may close.

