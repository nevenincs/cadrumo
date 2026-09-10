---
tags:
  - '#plan'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
tier: L3
related:
  - '[[2026-09-10-registry-authority-artifact-boundary-adr]]'
  - '[[2026-09-10-registry-authority-artifact-boundary-research]]'
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:e999b5841a10d8b597fbb8762109cbfc444cd2e9810660d0ea61abfe387b3b44'
---

# `registry-authority-artifact-boundary` plan

Publish a validated immutable authority artifact, consume it exclusively at runtime, and prove the packaged boundary through real workflows.

## Description

The accepted immutable-runtime-publication decision governs all Waves. Wave W01 defines publication, Wave W02 changes the runtime authority path, and Wave W03 removes package coupling and verifies the release boundary. The plan uses only publication and installed-workflow behavior as proof; it does not encode implementation shape as an oracle.

## Steps

## Wave `W01` - Publishable authority format

Establish the complete artifact format and the development publisher that produces it before runtime switches to that contract.

### Phase `W01.P01` - Artifact contract

Define the versioned, digest-verified immutable authority representation and its failure semantics.

- [x] `W01.P01.S01` - Implement the artifact reader and writer contract; `src/cadrumo/domain/calculations/registry/authority_artifact.py`.

### Phase `W01.P02` - Development publication

Make development validation publish an artifact atomically without using runtime fallback semantics.

- [ ] `W01.P02.S02` - Publish validated registry candidates as authority artifacts; `dev/registry/pipeline/`.

## Wave `W02` - Artifact-only runtime

Switch bundled runtime authority to artifact consumption and remove its raw authoring loader path.

### Phase `W02.P03` - Runtime authority

Construct bundled authority from the published artifact and fail before work when the artifact is invalid.

- [ ] `W02.P03.S03` - Replace bundled source compilation with artifact loading; `src/cadrumo/domain/calculations/registry/authority.py`.
- [ ] `W02.P03.S04` - Remove runtime compiler cache and raw loader exposure; `src/cadrumo/domain/calculations/registry/loader.py`.

## Wave `W03` - Package boundary and proof

Exclude authoring inputs from the shipped package and prove the release boundary with installed behavioral workflows.

### Phase `W03.P04` - Packaging and development relocation

Place compiler and conformance code in development dependencies and package only runtime assets.

- [ ] `W03.P04.S05` - Restrict distribution contents to runtime authority assets; `pyproject.toml`.
- [ ] `W03.P04.S06` - Relocate registry authoring tests and compiler-only modules; `src/cadrumo/domain/calculations/registry/`.

### Phase `W03.P05` - Behavioral release gates

Exercise publication refusal, artifact-only installed use, corruption refusal, and post-publication source isolation.

- [ ] `W03.P05.S07` - Prove artifact publication and installed runtime behavior; `tests/integration/`.
- [ ] `W03.P05.S08` - Document the artifact publication and recovery workflow; `docs/`.

## Parallelization

Waves are ordered: the publisher contract precedes the artifact-only runtime, which precedes package exclusion and installed proof. Within W03, packaging relocation and behavioral-gate preparation may proceed independently once W02 is complete.

## Verification

Publication of a deliberately defective candidate is refused without changing the published artifact. A built and isolated package, with authoring TOML and record-design corpus absent, completes an actual CLI workflow. A missing or corrupted artifact fails before output and never recompiles sources. Changing development sources after publication leaves installed behavior unchanged until valid republishing. Each completed step receives review, and the final review has no unresolved high or critical finding.
