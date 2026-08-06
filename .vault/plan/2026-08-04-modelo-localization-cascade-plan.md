---
tags:
  - '#plan'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-05'
body_hash: 'sha256:a60ebf447b11e36449ac1ffc2feca4bbf51a763c6c9da97045545fc1ce2aa14e'
tier: L3
related:
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
  - '[[2026-08-04-modelo-localization-cascade-research]]'
  - '[[2026-08-04-modelo-localization-cascade-migration-feasibility-research]]'
  - '[[2026-08-05-modelo-localization-cascade-identical-source-adjudication-research]]'
  - '[[2026-08-05-modelo-localization-cascade-execution-closeout-audit]]'
---

# `modelo-localization-cascade` plan

## Description

This plan records the migration and certification boundary for the accepted root-only localization design. W01 was executed by the disposable migration work, and the root-only production cutover then landed in `ced27b5a59`. The remaining historical W02-W04 rows are reconciled below from the live loader/catalogue contracts and retained evidence; no disposable migration application or revision-local locale storage is to be restored.

> Reconciled 2026-08-05 - historical, not active. W02-W04 were superseded by
> the already-landed root-only shared-catalogue cutover. Their rows are closed
> by explicit Step Records and the execution closeout audit, with source-aware
> parity evidence and no claim of a post-disposal temporary-app rerun.

The historical insertion of `W01.P02.S18` intentionally preserves its
canonical identifier rather than renumbering existing Step Records. The plan
checker may therefore report `PLAN022` for this permitted insertion ordering;
moving the row would sever its `W01.P02` display path and produce `PLAN030`.

The normal operating mode is a dry run. Every dry run writes a deterministic, self-contained proposal to a temporary output directory containing the staged tree, source fingerprint, sealed manifest, conflicts, unresolved review register, parity report, and summary. The campaign is measured by verbatim Spanish extraction, a language-neutral schema, and stopping revision N+1 from re-declaring unchanged leaves; byte compression is not its success criterion. The application must refuse a live registry destination and must not expose a production mutation path before explicit certification evidence exists.

## Steps

## Parallelization

Waves are sequential: source extraction and classification precede the pre-emission review gate; the gate precedes staging; staging precedes parity; parity and review precede the disposable handoff. Within a phase, steps are sequential unless the executing agent proves that their inputs and outputs are disjoint. No step may modify live revision schemas or locale data. The eventual production cutover is outside this plan and requires a separate certified plan.

## Verification

The migration application is verified with real corpus data and real filesystem behavior. A dry run must be repeatable, must produce a manually reviewable temporary artifact, and must leave the live registry unchanged. The pre-emission review gate must surface mirrored-help and key-echo leaves for delete-versus-migrate adjudication and surface year-embedded label families for an explicit parameterization decision. The parity harness must cover every supported model, revision, casilla, localizable field, and supported locale; mismatches, unresolved candidates, source drift, and incomplete review must fail certification. The final gate also proves that live-registry destinations and non-certified production-write modes are rejected, and that retained evidence is sufficient to reproduce or audit the proposal after the disposable application is removed.

## Wave `W01` - Migration source contract

Pin the existing corpus and define the extraction and identity contract that the disposable application must preserve.

### Phase `W01.P01` - Corpus fingerprint and extraction

Capture the complete existing localization corpus through the current loader without changing production data.

- [x] `W01.P01.S01` - Pin the corpus fingerprint and supported revision inventory; `dev/registry/migration`.
- [x] `W01.P01.S02` - Extract the current resolved localization matrix without mutating production data; `dev/registry/migration`.

### Phase `W01.P02` - Identity and classification manifest

Produce deterministic canonical candidates, exact occurrence records, unresolved review entries, and source hashes. Before emission, review must explicitly adjudicate placeholder debt as delete-versus-migrate and decide whether year-embedded label families need a parameterized-label ADR amendment; no emitter may silently harden either choice.

- [x] `W01.P02.S03` - Generate canonical occurrence candidates from model, revision, casilla, and field identity; `dev/registry/migration`.
- [x] `W01.P02.S04` - Classify candidates as grounded, revision-exact, or continuity-candidate without promoting provisional identity; `dev/registry/migration`.
- [x] `W01.P02.S05` - Emit a sealed source manifest and unresolved review register with hashes, drift fields, and leaf state; `dev/registry/migration`.
- [x] `W01.P02.S18` - Resolve placeholder debt and year-parameterized label decisions before emission; `dev/registry/migration and the authorizing ADR/research records`.

## Wave `W02` - Staged migration emitter

Construct a root-catalogue emitter and a dry-run output boundary that never writes into the live registry.

### Phase `W02.P03` - Root catalogue staging emission

Emit language-neutral revision schemas and root-only locale catalogues into an isolated staging tree.

- [x] `W02.P03.S06` - Emit language-neutral revision staging data and root Spanish catalogues into an isolated output tree; reconciled by `ced27b5a59` and its Step Record; `dev/registry/migration`.
- [x] `W02.P03.S07` - Emit explicit applicability variants, exact occurrence entries, and tombstones that preserve prior fallback behavior; reconciled by the production exact-to-continuidad resolver and its Step Record; `dev/registry/migration`.

### Phase `W02.P04` - Dry-run artifact boundary

Make every proposed outcome reviewable in a temporary output directory and refuse live-registry writes.

- [x] `W02.P04.S08` - Implement a dry-run command with an explicit temporary-output contract and no live-registry destination; superseded by disposal after `ced27b5a59`; `dev/registry/migration`.
- [x] `W02.P04.S09` - Save a deterministic artifact bundle containing the proposed tree, manifest, conflicts, unresolved review, and source fingerprint; reconciled by retained W01 and vault evidence; `dev/registry/migration`.
- [x] `W02.P04.S10` - Reject live-registry paths and every non-certified production-write mode during migration-app execution; resolved by removal of the migration write surface and the new-Modelo guard; `dev/registry/migration`.

## Wave `W03` - Parity and certification

Prove proposed resolution parity across the complete supported corpus and produce reviewable certification evidence.

### Phase `W03.P05` - Resolver parity harness

Compare the staged resolver against the current resolved behavior for every supported model, revision, casilla, field, and locale.

- [x] `W03.P05.S11` - Implement the staged root-catalogue resolver with locale fallback rules isolated from production; resolved by the live canonical resolver; `dev/registry/migration`.
- [x] `W03.P05.S12` - Compare old and proposed resolved values across every supported model, revision, casilla, field, and locale; reconciled by bounded parity and source-aware locale evidence; `dev/registry/migration`.

### Phase `W03.P06` - Manual review and certification gate

Require reviewable evidence, explicit disposition of unresolved candidates, and zero unapproved parity differences.

- [x] `W03.P06.S13` - Record every mismatch and candidate continuity decision as an explicit review disposition; resolved by the identical-source adjudication register and retained continuity review boundary; `dev/registry/migration`.
- [x] `W03.P06.S14` - Enforce certification on source-hash agreement, complete review disposition, zero unapproved mismatches, and full parity; resolved by current status/audit gates with zero pending equalities; `dev/registry/migration`.

## Wave `W04` - Disposable handoff

Package the application for controlled review and explicitly defer any production cutover to a certified follow-on decision.

### Phase `W04.P07` - Production refusal and handoff package

Keep production mutation unavailable until an explicit certified follow-on plan authorizes cutover.

- [x] `W04.P07.S15` - Produce a follow-on cutover handoff that cannot execute production mutation from the disposable application; superseded by the completed cutover and disposal; `dev/registry/migration`.

### Phase `W04.P08` - Disposable lifecycle evidence

Document isolation, repeatability, deletion, and retained evidence for the disposable migration application.

- [x] `W04.P08.S16` - Add real-behavior repeatability, temporary-output, and no-live-write tests for the dry-run boundary; reconciled by retained real-behavior gates and final no-legacy boundary; `tests/cadrumo/domain/calculations/registry`.
- [x] `W04.P08.S17` - Package disposal and evidence-retention instructions, then run the migration-application validation gate; resolved by `ced27b5a59` and retained vault evidence; `dev/registry/migration`.
