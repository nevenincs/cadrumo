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
body_hash: 'sha256:95ad5e5da14e738752a532d0cfc2b83d86d7450c903a69e6d4ca18226950c2f4'
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
- [ ] `S02` - Remove or relocate unused core and persistence helpers with all callers updated; `src/cadrumo/core and src/cadrumo/adapters/persistence and their tests`.
- [ ] `S03` - Remove unused application and command helpers and verify real operator paths; `src/cadrumo/application and src/cadrumo/entrypoints and their tests`.
- [ ] `S04` - Resolve all remaining method and data candidates through their actual contracts; `src/cadrumo/domain, application, adapters and entrypoints and owning tests`.
- [ ] `S05` - Consolidate verified operation and presentation duplication; `src/cadrumo/application/live, operations, ledger and entrypoints/cli`.
- [ ] `S06` - Consolidate verified domain and adapter duplication while preserving boundary semantics; `src/cadrumo/domain and src/cadrumo/adapters and owning tests`.
- [ ] `S07` - Remeasure all audit gates, repair remaining verification defects and complete integrated review; `dev/quality, source tests, audit run evidence and plan`.

## Parallelization

Execute sequentially in this session. No delegated workers. Preserve concurrent external work and keep shared metadata generation after source changes settle.

## Verification

Every current finding is resolved through its owning mechanism and remeasured, with any unresolved condition kept visible. Run covering behavior tests, style, format, configured type checks and import boundaries. Exercise planted negative controls for scanner changes. Exact unused-symbol/export gates must pass, duplication must be remeasured, and heuristic findings must retain honest evidence. Close only verified steps and perform the integrated final review before reporting completion.
