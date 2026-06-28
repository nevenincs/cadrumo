---
tags:
  - '#plan'
  - '#docs-navigability'
date: '2026-06-01'
modified: '2026-06-01'
tier: L3
related:
  - '[[2026-05-30-docs-architecture-plan]]'
  - '[[2026-05-30-docs-architecture-research]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
  - '[[2026-06-04-docs-navigability-adr]]'
  - '[[2026-06-04-docs-navigability-research]]'
---








# `docs-navigability` `documentation navigability cross-link campaign` plan

## Wave `W01` - core-struct spine gate

Enforce that modules importing a canonical core struct cross-link it, so the API docs steer readers to the spine. Delivered as a docs-lane hard-cut gate driven to zero across two anchor tiers.


### Phase `W01.P01` - spine anchors and enforcement

Build the gate, broaden the anchor set, and codify the selection criterion.

- [x] `W01.P01.S01` - Build the core-struct navigability gate enforcing import-implies-link, drive 162 to 0; `src/aeat/tests/test_docstring_core_struct_links.py`.
- [x] `W01.P01.S02` - Broaden the anchor set from 9 to 28 via in-degree, RAG, and a discovery swarm, drive 255 to 0; `src/aeat/tests/test_docstring_core_struct_links.py`.
- [x] `W01.P01.S03` - Codify the anchor-selection criterion as a project rule; `.vaultspec/rules/rules/project/core-struct-docstring-links.md`.

## Wave `W02` - return-type linking gate

Extend navigability along the highest-signal collaborator edge: every documented public function must cross-link its aeat-typed return annotation. Hard-cut docs-lane gate, swarm remediation.

### Phase `W02.P02` - return-type gate and remediation

Build the return-type gate, remediate via swarm, verify green.

- [x] `W02.P02.S04` - Build the return-type linking gate enumerating unlinked aeat-typed return annotations; `src/aeat/tests/test_docstring_return_type_links.py`.
- [x] `W02.P02.S05` - Remediate the return-type violations via a partitioned sonnet swarm, drive to 0; `src/aeat/application`.
- [x] `W02.P02.S06` - Verify the return-type gate, the stub correspondence, and the offline nitpicky build are green; `docs/conf.py`.

## Wave `W03` - parameter-type linking gate

Extend the signature-link gate to parameter annotations, scoped to avoid obvious or low-value links, completing the collaborator graph for public API symbols.

### Phase `W03.P03` - parameter-type gate and remediation

Extend to parameter annotations, remediate via swarm, verify green.

- [x] `W03.P03.S07` - Extend the signature-link gate to parameter annotations, scoped to high-value links; `src/aeat/tests/test_docstring_return_type_links.py`.
- [x] `W03.P03.S08` - Remediate the parameter-type violations via a partitioned swarm, drive to 0; `src/aeat/domain`.
- [x] `W03.P03.S09` - Verify the parameter-type gate and the offline nitpicky build are green; `docs/conf.py`.

## Description


## Steps







## Parallelization


## Verification

