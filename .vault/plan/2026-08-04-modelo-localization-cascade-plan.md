---
tags:
  - '#plan'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_hash: 'sha256:3fbf3f52a8ed0c96153b3aed71f6f0c276ea2fbb15d0eefb0e3a9e0bc715e8be'
tier: L3
related:
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-research]]'
  - '[[2026-08-04-modelo-localization-cascade-migration-feasibility-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `modelo-localization-cascade` plan

## Description

This plan constructs and certifies a disposable migration application for the accepted root-only localization design. It deliberately stops short of production cutover. The application must extract the existing revision-local corpus, propose the root catalogue and revision-schema outcome, preserve unresolved semantic decisions for manual review, and prove old-versus-new resolution parity before any future cutover plan is considered.

The normal operating mode is a dry run. Every dry run writes a deterministic, self-contained proposal to a temporary output directory containing the staged tree, source fingerprint, sealed manifest, conflicts, unresolved review register, parity report, and summary. The application must refuse a live registry destination and must not expose a production mutation path before explicit certification evidence exists.

## Steps

## Parallelization

Waves are sequential: source extraction and classification precede staging; staging precedes parity; parity and review precede the disposable handoff. Within a phase, steps are sequential unless the executing agent proves that their inputs and outputs are disjoint. No step may modify live revision schemas or locale data. The eventual production cutover is outside this plan and requires a separate certified plan.

## Verification

The migration application is verified with real corpus data and real filesystem behavior. A dry run must be repeatable, must produce a manually reviewable temporary artifact, and must leave the live registry unchanged. The parity harness must cover every supported model, revision, casilla, localizable field, and supported locale; mismatches, unresolved candidates, source drift, and incomplete review must fail certification. The final gate also proves that live-registry destinations and non-certified production-write modes are rejected, and that retained evidence is sufficient to reproduce or audit the proposal after the disposable application is removed.

## Wave `W01` - Migration source contract

Pin the existing corpus and define the extraction and identity contract that the disposable application must preserve.

### Phase `W01.P01` - Corpus fingerprint and extraction

Capture the complete existing localization corpus through the current loader without changing production data.

- [x] `W01.P01.S01` - Pin the corpus fingerprint and supported revision inventory; `dev/registry/migration`.
- [ ] `W01.P01.S02` - Extract the current resolved localization matrix without mutating production data; `dev/registry/migration`.

### Phase `W01.P02` - Identity and classification manifest

Produce deterministic canonical candidates, exact occurrence records, unresolved review entries, and source hashes.

- [ ] `W01.P02.S03` - Generate canonical occurrence candidates from model, revision, casilla, and field identity; `dev/registry/migration`.
- [ ] `W01.P02.S04` - Classify candidates as grounded, revision-exact, or continuity-candidate without promoting provisional identity; `dev/registry/migration`.
- [ ] `W01.P02.S05` - Emit a sealed source manifest and unresolved review register with hashes, drift fields, and leaf state; `dev/registry/migration`.

## Wave `W02` - Staged migration emitter

Construct a root-catalogue emitter and a dry-run output boundary that never writes into the live registry.

### Phase `W02.P03` - Root catalogue staging emission

Emit language-neutral revision schemas and root-only locale catalogues into an isolated staging tree.

- [ ] `W02.P03.S06` - Emit language-neutral revision staging data and root Spanish catalogues into an isolated output tree; `dev/registry/migration`.
- [ ] `W02.P03.S07` - Emit explicit applicability variants, exact occurrence entries, and tombstones that preserve prior fallback behavior; `dev/registry/migration`.

### Phase `W02.P04` - Dry-run artifact boundary

Make every proposed outcome reviewable in a temporary output directory and refuse live-registry writes.

- [ ] `W02.P04.S08` - Implement a dry-run command with an explicit temporary-output contract and no live-registry destination; `dev/registry/migration`.
- [ ] `W02.P04.S09` - Save a deterministic artifact bundle containing the proposed tree, manifest, conflicts, unresolved review, and source fingerprint; `dev/registry/migration`.
- [ ] `W02.P04.S10` - Reject live-registry paths and every non-certified production-write mode during migration-app execution; `dev/registry/migration`.

## Wave `W03` - Parity and certification

Prove proposed resolution parity across the complete supported corpus and produce reviewable certification evidence.

### Phase `W03.P05` - Resolver parity harness

Compare the staged resolver against the current resolved behavior for every supported model, revision, casilla, field, and locale.

- [ ] `W03.P05.S11` - Implement the staged root-catalogue resolver with locale fallback rules isolated from production; `dev/registry/migration`.
- [ ] `W03.P05.S12` - Compare old and proposed resolved values across every supported model, revision, casilla, field, and locale; `dev/registry/migration`.

### Phase `W03.P06` - Manual review and certification gate

Require reviewable evidence, explicit disposition of unresolved candidates, and zero unapproved parity differences.

- [ ] `W03.P06.S13` - Record every mismatch and candidate continuity decision as an explicit review disposition; `dev/registry/migration`.
- [ ] `W03.P06.S14` - Enforce certification on source-hash agreement, complete review disposition, zero unapproved mismatches, and full parity; `dev/registry/migration`.

## Wave `W04` - Disposable handoff

Package the application for controlled review and explicitly defer any production cutover to a certified follow-on decision.

### Phase `W04.P07` - Production refusal and handoff package

Keep production mutation unavailable until an explicit certified follow-on plan authorizes cutover.

- [ ] `W04.P07.S15` - Produce a follow-on cutover handoff that cannot execute production mutation from the disposable application; `dev/registry/migration`.

### Phase `W04.P08` - Disposable lifecycle evidence

Document isolation, repeatability, deletion, and retained evidence for the disposable migration application.

- [ ] `W04.P08.S16` - Add real-behavior repeatability, temporary-output, and no-live-write tests for the dry-run boundary; `tests/cadrumo/domain/calculations/registry`.
- [ ] `W04.P08.S17` - Package disposal and evidence-retention instructions, then run the migration-application validation gate; `dev/registry/migration`.
