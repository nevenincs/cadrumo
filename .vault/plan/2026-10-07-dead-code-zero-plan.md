---
tags:
  - '#plan'
  - '#dead-code-zero'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]'
  - '[[2026-09-04-reachability-burndown-adr]]'
  - '[[2026-10-05-google-outbound-review-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:268204cf841d5287403a45cc74aefb34d8322f2a41d0475100fc4fe8f33407c1'
---

# `dead-code-zero` plan

## Description

Approved 2026-10-07

The user authorized rerunning the dead-code audit and continuing until the code is resolved, following explicit authorization to remove unsupported Sheets reads and either remove or genuinely connect other capabilities. The measured baseline has zero unreachable modules, zero exact findings, twenty symbol candidates and one Vulture finding. Retire unused product APIs without inventing consumers; preserve genuine framework hooks, declared native generation inputs and installed acceptance cleanup by improving structural analysis.

The accepted quality-gate product-boundary and reachability burndown ADRs govern S01-S03. The accepted Google outbound review ADR governs Google removals in S01 and preservation of saved-review cleanup in S02. These are implementation and analyzer accuracy changes within accepted decisions; no uncovered costly decision is proposed.

## Steps

- [x] `S01` - Retire unused product APIs, obsolete result fields and unimplemented transport/error declarations while preserving live custody and publication behavior; `src/cadrumo/adapters/outbound/google, src/cadrumo/adapters/persistence/storage, src/cadrumo/application/user_profile, src/cadrumo/entrypoints/runtime, src/cadrumo/core/transport_locus.py and owning tests`.
- [ ] `S02` - Resolve logging hooks, native generation records and typed acceptance cleanup through structural analyzer coverage and compatible formatter handling; `dev/audit reachability analyzers and tests, src/cadrumo/core/diagnostic_log.py and owning tests`.
- [ ] `S03` - Re-measure dead-code signals, resolve cascading findings, run configured checks and record integrated closure; `.vault/audit/2026-10-07-dead-code-zero-tooling-coverage-audit.md, affected dead-code source and tests, .vault/plan/2026-10-07-dead-code-zero-plan.md`.

## Parallelization

Execute S01, S02 and S03 sequentially in this worktree. Preserve unrelated changes and use scoped commits. No delegated work is planned.

## Verification

The Python product population remains fully covered. Reachability reports zero unreachable, type-only, module-execution-only and orphan-test modules, zero exact findings and zero unresolved heuristic candidates. Vulture reports zero findings and export-consumption remains clean. Native Rust, C, CMake and binary artifacts retain explicit scope exclusion; generated-contract Python consumers are analyzed accurately.

Owning persistence, runtime, Google and CLI/TUI tests pass after removals. Analyzer tests prove qualified positive consumers and retain findings for unrelated classes, arbitrary methods and unresolved receivers. Configured formatting, lint, type and quality checks pass for the final source state. Append the measured outcome and final integrated review to the existing dead-code audit, then close each Step through the owning CLI.
