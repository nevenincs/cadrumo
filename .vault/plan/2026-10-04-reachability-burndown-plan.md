---
tags:
  - '#plan'
  - '#reachability-burndown'
date: '2026-10-04'
tier: L1
related:
  - '[[2026-09-04-reachability-burndown-adr]]'
  - '[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]'
  - '[[2026-09-11-justfile-design-adr]]'
  - '[[2026-07-01-import-centralization-adr]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:97e32189d992e9aedd52ca82a38671c686aa7a38922010a2db0db79ba7b9a6bc'
---

# `reachability-burndown` plan

Resolve all current dead-weight and unused-code findings through their actual owners.

## Description

Approved 2026-10-04

Authorization: the operator instructed "Action all the findings" after the audit-tooling repair and current results. This covers all current reachability candidates, duplication clones, exact unused symbols/exports, and remaining verification defects. Preserve concurrent registry and type-harness changes. No external publication or remote Git actions are authorized.

The accepted reachability-burndown decision governs all steps: delete dead implementations, move genuine development-only tools to their owner, wire missing product behavior, or resolve dynamic use through live structural declarations. No exception identities, thresholds, dispositions consumed by code, or ceremonial references. The quality boundary and Just decisions govern S01 and S07; import centralization governs all relocation and consolidation. Existing duplication-remediation work is reused where applicable rather than overwritten. No new costly decision is currently needed.

The prior measurement had 291 candidates, 11 exact functions, 20 clones, no unreachable modules, and no Vulture findings. These are leads, not acceptance constants. S01 refreshes the live source. The active worktree contains other authorized work; scope commits by actual ownership and do not overwrite shared changes.

## Steps

- [x] `S01` - Refresh the full finding population and resolve assigned-validator and framework-dispatch evidence; `dev/audit/unreachable_*.py and dev/audit/tests`.
- [x] `S02` - Remove or relocate unused core and persistence helpers with all callers updated; `src/cadrumo/core and src/cadrumo/adapters/persistence and their tests`.
- [x] `S03` - Remove unused application and command helpers and verify real operator paths; `src/cadrumo/application and src/cadrumo/entrypoints and their tests`.
- [x] `S04` - Retire unused domain and adapter doors, activate the declared expense validator, and resolve schema and qualified member consumers; `dev/audit, source owners and focused tests`.
- [x] `S08` - Resolve typed receiver and dataclass serialization visibility, distinguish development tests, retire uncalled wrappers and relocate remaining core and profile test helpers; `dev/audit, core observability and logging, profile snapshots, Modelo 036, withholding and Renta predicates with owning tests`.
- [x] `S09` - Resolve newly exact unused functions and test-only catalogue projections, wire the canonical JSON envelope emitter, repair private locale-key visibility and remove obsolete translations; `Core JSON contracts, operator and aggregation helpers, registry fixture owners, locale discovery and catalogues, conformance isolation and owning tests`.
- [x] `S11` - Retire unsupported LLM summary and cache display doors and the legacy corpus-reference lookup; `LLM persistence and owning tests, citation lookup and owning tests`.
- [x] `S12` - Resolve explicit type-alias schema visibility and remove uncalled domain and filing convenience doors; `dev/audit schema consumer analysis, domain record predicates, filing runtime and owning tests`.
- [x] `S13` - Retire TUI properties used only for test introspection while preserving real presentation and retained cancellation facts; `TUI app, screen hosts, workbench and automation screens with owning and development tests`.
- [x] `S14` - Retire uncalled core dictionary conversion and date aliases, move the Google test predicate to its actual fixture owner and project only consumed native audit-token coordinates; `Core configuration and locales, AEAT workspace, native audit token decoding and owning tests`.
- [x] `S15` - Bind Windows worker admission to retained process birth and exact Job membership and retire unsupported native and browser test doors; `Native worker identity, enrollment and shutdown fixture owners, browser authentication and owning tests`.
- [ ] `S16` - Retire legacy secure batch wrappers and move diagnostic observation-history and index inspection to their real fixture owners; `Secure object batches, observation repositories, transaction index probes and owning fixtures`.
- [ ] `S17` - Resolve homogeneous iterable receiver evidence without clearing shadowed or unknown element types; `Reachability receiver analysis, outside consumers and planted controls`.
- [ ] `S10` - Resolve the remaining unused methods and data members through actual product and fixture owners; `src/cadrumo, dev/audit and owning tests`.
- [x] `S05` - Consolidate verified operation and presentation duplication; `src/cadrumo/application/live, operations, ledger and entrypoints/cli`.
- [x] `S06` - Consolidate verified domain and adapter duplication while preserving boundary semantics; `src/cadrumo/domain and src/cadrumo/adapters and owning tests`.
- [ ] `S07` - Remeasure all audit gates, repair remaining verification defects and complete integrated review; `dev/quality, source tests, audit run evidence and plan`.

## Parallelization

Execute sequentially in this session. No delegated workers. Preserve concurrent external work and keep shared metadata generation after source changes settle.

## Verification

Every current finding is resolved through its owning mechanism and remeasured, with any unresolved condition kept visible. Run covering behavior tests, style, format, configured type checks and import boundaries. Exercise planted negative controls for scanner changes. Exact unused-symbol/export gates must pass, duplication must be remeasured, and heuristic findings must retain honest evidence. Close only verified steps and perform the integrated final review before reporting completion.
