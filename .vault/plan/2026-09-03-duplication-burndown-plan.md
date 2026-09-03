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
body_hash: 'sha256:1a02f8b30cb73a88e9faf6d78047bdb47e857a147d490a0a0b825afda18cc73e'
---

<!-- RETIRED: P02, S03, S06 -->

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

### Phase `W01.P03` - freeze the live evidence graph

Capture one stable 52-clone snapshot and classify connected components, ownership, and intended treatment before source edits.

- [ ] `W01.P03.S07` - Define minimal typed builders for repeated Ledger leaf invocation and result schema declarations; `src/cadrumo/entrypoints/cli/_app_ledger_command_spec_support.py`.

### Phase `W01.P04` - freeze the live evidence graph

Capture a stable clone snapshot and classify its connected components before editing source.


### Phase `W01.P17` - reconcile live evidence

Reconcile historical dispositions against one stable live scan without suppressing or baselining findings.


## Wave `W02` - reduce CLI declaration clones

Reduce the dominant CLI clone family through dependency-graph-bounded primitives while preserving each command contract; semantic-risk work waits for this high-volume family to stabilize.

### Phase `W02.P05` - design command declaration primitives

Introduce only the minimal typed declaration primitives justified by repeated Ledger command semantics and prove contract equivalence.


### Phase `W02.P06` - design declaration primitives

Define only typed CLI declaration primitives justified by repeated command semantics.


### Phase `W02.P08` - reduce Ledger command clusters

Migrate graph-bounded Ledger CommandSpec components with contract proof after each batch.


### Phase `W02.P09` - reduce Ledger command clusters

Migrate Ledger CommandSpec components in bounded batches with focused command-contract verification after each batch.


### Phase `W02.P10` - reduce remaining CLI pairs

Resolve the three non-Ledger CLI pairs without coupling unrelated command families.


### Phase `W02.P12` - reduce remaining CLI pairs

Resolve the three non-Ledger CLI clone pairs without coupling unrelated command families.


### Phase `W02.P22` - ledger command specifications

Consolidate exact Ledger parameter records by dependency-connected family and verify the materialized command graph after each component.


## Wave `W03` - resolve semantic-risk clone pairs

Adjudicate and repair each non-CLI semantic pair independently so shared concepts are centralized without merging merely similar authorities.

### Phase `W03.P07` - resolve application-local pairs

Resolve each application-local pair at its owning boundary.


### Phase `W03.P11` - resolve AEAT adapter pair

Centralize shared check mechanics while retaining protocol-specific behavior.


### Phase `W03.P13` - resolve TUI Ledger pair

Remove duplicated controller and route behavior at the owning TUI boundary.


### Phase `W03.P14` - resolve application-local pairs

Treat each application-local pair according to its owning boundary and established authority.


### Phase `W03.P15` - resolve registry binding pair

Unify binding declarations only where registry and calculation semantics are identical.


### Phase `W03.P16` - resolve AEAT adapter pair

Centralize only the shared NIF and GROI check mechanics while preserving protocol-specific behavior and evidence.


### Phase `W03.P19` - resolve TUI Ledger pair

Remove duplicated controller and routing behavior at the owning TUI boundary.


### Phase `W03.P21` - resolve registry binding pair

Unify the shared Ledger to Renta binding declaration only where registry authority and calculation semantics are identical.


## Wave `W04` - prove and reconcile honest green

Run focused and repository-wide gates, reconcile every residual clone, and close only with stable evidence and no detector weakening.

### Phase `W04.P18` - verify gates

Prove detector teeth and run focused, subsystem, and full repository gates.


### Phase `W04.P20` - reconcile closure

Re-audit every residual clone and record final dispositions and closure evidence.


## Wave `W05` - restore trustworthy duplication evidence

Recover the live disposition ledger and freeze reproducible clone evidence before changing product code; every later Wave depends on this authority.

## Wave `W06` - consolidate declarative CLI contracts

Reduce the dominant CommandSpec clone family through narrow typed constants and constructors while preserving every public CLI token, help key, policy, binding, and result schema.

## Parallelization

## Verification
