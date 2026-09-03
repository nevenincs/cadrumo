---
tags:
  - '#plan'
  - '#duplication-burndown'
date: '2026-09-03'
tier: L3
related:
  - '[[2026-07-14-honest-all-green-adr]]'
  - '[[2026-07-17-duplication-evidence-repair-adr]]'
  - '[[2026-07-17-duplication-evidence-repair-plan]]'
  - '[[2026-09-03-duplication-burndown-honest-clone-closure-research]]'
modified: '2026-09-03'
body_schema: body-v2
body_hash: 'sha256:7de84dd47cc5ea685f14ab03e1705c3b1f03c1412d3dfdb3a7562befb23ca961'
---

<!-- RETIRED: W05, W06, W07, P02, P03, P04, P06, P09, P12, P14, P16, P17, P19, P20, P21, P22, P23, P24, P25, P26, P27, S03, S06, S07 -->

# `duplication-burndown` plan

## Description

Burn down every currently observed production clone from one stable evidence set while preserving semantic ownership and public contracts. Wave W01 restores the disposition authority established by the duplication evidence repair decision. Wave W02 addresses the dominant immutable CLI declaration family through narrow typed reuse. Wave W03 gives each behavior-bearing pair an independent ownership decision. Wave W04 reconciles the final evidence and proves repository-wide health under the honest-all-green constraints.

## Steps

## Wave `W01` - restore trustworthy evidence

Re-establish stable clone evidence and historical dispositions without weakening the detector; every reduction wave depends on this authority.

### Phase `W01.P01` - recover disposition memory

Recover the deleted disposition registry and audit tests from history, then reconcile renamed locators against the current tree.

- [x] `W01.P01.S01` - Recover the historical clone dispositions from the last trustworthy revision without accepting stale locators or counts; `dev/audit/duplication_dispositions.toml`.
- [x] `W01.P01.S02` - Restore and run the deleted duplication instrument tests against the current typed runner; `src/cadrumo/tests/test_dev_audit_report.py`.
- [x] `W01.P01.S04` - Recover and reconcile one disposition for every currently observed clone group without carrying stale groups or muting findings; `dev/audit/duplication_dispositions.toml`.
- [x] `W01.P01.S05` - Prove disposition parsing and live-clone reconciliation preserve unavailable and changed-scan failures as non-green evidence; `dev/audit/tests`.

## Wave `W02` - reduce CLI declaration clones

Reduce the dominant CLI clone family through dependency-graph-bounded primitives while preserving each command contract; semantic-risk work waits for this high-volume family to stabilize.

### Phase `W02.P05` - design command declaration primitives

Introduce only the minimal typed declaration primitives justified by repeated Ledger command semantics and prove contract equivalence.

- [x] `W02.P05.S08` - Define narrowly typed reusable Ledger parameter declarations and prove immutable CommandSpec equality; `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`.

### Phase `W02.P08` - reduce Ledger command clusters

Migrate graph-bounded Ledger CommandSpec components with contract proof after each batch.

- [x] `W02.P08.S09` - Consolidate the lifecycle and operations clone component while preserving every command token, help key, policy, handler, and schema; `src/cadrumo/entrypoints/cli`.
- [ ] `W02.P08.S10` - Consolidate the evidence, foundation, classification, and counterparty clone components with focused command graph proofs; `src/cadrumo/entrypoints/cli`.

### Phase `W02.P10` - reduce remaining CLI pairs

Resolve the three non-Ledger CLI pairs without coupling unrelated command families.

- [ ] `W02.P10.S11` - Resolve the Modelo nonwork CommandSpec pairs through their narrow shared declaration authority; `src/cadrumo/entrypoints/cli`.
- [ ] `W02.P10.S12` - Resolve the Modelo export and review package clone without coupling distinct workflows; `src/cadrumo/entrypoints/cli`.

## Wave `W03` - resolve semantic-risk clone pairs

Adjudicate and repair each non-CLI semantic pair independently so shared concepts are centralized without merging merely similar authorities.

### Phase `W03.P07` - resolve application-local pairs

Resolve each application-local pair at its owning boundary.

- [ ] `W03.P07.S13` - Adjudicate and resolve the three application-local clone pairs with focused invariant tests; `src/cadrumo/application`.

### Phase `W03.P11` - resolve AEAT adapter pair

Centralize shared check mechanics while retaining protocol-specific behavior.

- [ ] `W03.P11.S14` - Adjudicate and resolve the GROI and NIF IVA check pair without merging distinct AEAT protocol authority; `src/cadrumo/adapters/outbound/aeat/sede`.

### Phase `W03.P13` - resolve TUI Ledger pair

Remove duplicated controller and route behavior at the owning TUI boundary.

- [ ] `W03.P13.S15` - Resolve the Ledger controller and route factory clone while preserving dependency injection and refresh ownership; `src/cadrumo/entrypoints/tui/ledger`.

### Phase `W03.P15` - resolve registry binding pair

Unify binding declarations only where registry and calculation semantics are identical.

- [ ] `W03.P15.S16` - Adjudicate the Ledger Renta binding declarations against registry authority and consolidate only their shared concept; `src/cadrumo/domain/calculations/registry`.

## Wave `W04` - prove and reconcile honest green

Run focused and repository-wide gates, reconcile every residual clone, and close only with stable evidence and no detector weakening.

### Phase `W04.P18` - verify gates

Prove detector teeth and run focused, subsystem, and full repository gates.

- [ ] `W04.P18.S17` - Reconcile final dispositions to the live clone set and remove entries for resolved groups; `dev/audit/duplication_dispositions.toml`.
- [ ] `W04.P18.S18` - Run duplication, import, semantic, architecture, type, lint, focused, and full quality gates without threshold or exclusion changes; `dev/audit/.runs`.

## Parallelization

Waves are ordered. Within W02, P08 follows P05; P10 may proceed after P05 when it does not edit the same support module. The four W03 phases may run in parallel because their source ownership does not overlap, but each receives an independent review before landing. W04 begins only after all accepted reductions and intentional dispositions are stable. Executors must check the shared worktree before every step and must not modify peer-owned dirty files.

## Verification

- One live `just audit-duplication` run is reproducible and every reported clone has exactly one current disposition during the campaign.
- Focused command-graph snapshots prove that CLI tokens, help keys, policies, handlers, parameter defaults, and result schemas remain unchanged.
- Each behavior-bearing consolidation has focused invariant tests and an independent code review with no unresolved HIGH or CRITICAL finding.
- The final duplication report contains zero unexplained clone groups and no threshold, exclusion, baseline, skip, or allowlist weakening.
- Import, semantic-overlap, architecture, type, lint, focused test, and full repository gates pass from one stable revision.
- Every Step is closed through the plan CLI and has its required Step Record; Wave summaries record the verified evidence.
