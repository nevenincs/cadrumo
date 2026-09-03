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
modified: '2026-09-03'
body_schema: body-v2
body_hash: 'sha256:1918ff7ec1a62bfbeb63156f2131e25004c3ded8e42891101ed013df987f6292'
---

<!-- RETIRED: W05, W06, W07, P02, P03, P04, P06, P09, P12, P14, P16, P17, P19, P20, P21, P22, P23, P24, P25, P26, P27, S03, S06, S07 -->

# `duplication-burndown` plan

## Description

## Steps

## Wave `W01` - restore trustworthy evidence

Re-establish stable clone evidence and historical dispositions without weakening the detector; every reduction wave depends on this authority.

### Phase `W01.P01` - recover disposition memory

Recover the deleted disposition registry and audit tests from history, then reconcile renamed locators against the current tree.

- [ ] `W01.P01.S01` - Recover the historical clone dispositions from the last trustworthy revision without accepting stale locators or counts; `dev/audit/duplication_dispositions.toml`.
- [ ] `W01.P01.S02` - Restore and run the deleted duplication instrument tests against the current typed runner; `src/cadrumo/tests/test_dev_audit_report.py`.
- [ ] `W01.P01.S04` - Recover and reconcile one disposition for every currently observed clone group without carrying stale groups or muting findings; `dev/audit/duplication_dispositions.toml`.
- [ ] `W01.P01.S05` - Prove disposition parsing and live-clone reconciliation preserve unavailable and changed-scan failures as non-green evidence; `dev/audit/tests`.

## Wave `W02` - reduce CLI declaration clones

Reduce the dominant CLI clone family through dependency-graph-bounded primitives while preserving each command contract; semantic-risk work waits for this high-volume family to stabilize.

### Phase `W02.P05` - design command declaration primitives

Introduce only the minimal typed declaration primitives justified by repeated Ledger command semantics and prove contract equivalence.

- [ ] `W02.P05.S08` - Define narrowly typed reusable Ledger parameter declarations and prove immutable CommandSpec equality; `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`.

### Phase `W02.P08` - reduce Ledger command clusters

Migrate graph-bounded Ledger CommandSpec components with contract proof after each batch.

- [ ] `W02.P08.S09` - Consolidate the lifecycle and operations clone component while preserving every command token, help key, policy, handler, and schema; `src/cadrumo/entrypoints/cli`.
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


## Wave `W04` - prove and reconcile honest green

Run focused and repository-wide gates, reconcile every residual clone, and close only with stable evidence and no detector weakening.

### Phase `W04.P18` - verify gates

Prove detector teeth and run focused, subsystem, and full repository gates.


## Parallelization

## Verification
