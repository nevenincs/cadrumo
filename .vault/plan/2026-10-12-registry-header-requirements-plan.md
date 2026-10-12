---
tags:
  - '#plan'
  - '#registry-header-requirements'
date: '2026-10-12'
tier: L1
related:
  - '[[2026-10-12-registry-header-requirements-adr]]'
modified: '2026-10-12'
body_schema: body-v2
body_hash: 'sha256:6ad02942c594ba9d4a2b38fc555a531eb4f1ae4eee274bc60539a18518749f52'
---

# `registry-header-requirements` plan

Make Modelo 111 export refuse a missing declarant identity, ejercicio or periodo through a reviewed, source-cited requirement in the semantic map.

## Description

Approved 2026-10-12. Basis: the owner's ruling of 2026-10-12, "i followw your recommedation", accepting the recommendation recorded in the governing ADR, and the operator's dispatch authorizing this plan's scaffold and execution under that ruling.

Decision coverage: `2026-10-12-registry-header-requirements-adr` (accepted) governs every Step; it refines the semantic-map authority of the generator ADR it links. S01 adds the requirement declaration to the semantic-map schema, its validation (catalogue, digest and quotation checks) and the generator's requirement derivation, with provenance carriage and tests including the uncited-requirement positive control. S02 declares the five Modelo 111 requirements, regenerates the 111 export target through the pipeline's republish route, and makes the export refusal name the profile fact rather than the producer key.

## Steps

- [x] `S01` - Extend the semantic-map schema, validation, generator and provenance with reviewed source-cited header requirements, with tests; `dev/registry/pipeline`.
- [ ] `S02` - Declare the cited Modelo 111 requirements, regenerate the 111 export target and name the missing profile fact in the export refusal; `dev/registry/mappings/modelo_111`.

## Parallelization

S02 depends on S01. No parallel execution.

## Verification

- `python -m dev.registry.pipeline check 111 2019-y-siguientes aeat-dr-111-2019-v18 2026 1T` reports `result=matched`.
- `dev/registry/pipeline/tests/test_reviewed_header_requirements.py` passes, including the rejection of an uncited requirement and of a quotation its source does not contain.
- `test_export_modelo_111_refuses_when_profile_name_missing` passes, with the refusal naming `identity.surnames or identity.legal_name`.
- Registry and export suites for 115, 117, 216 and 360 stay green; ruff, ruff format, ty and `just check-import-boundaries` pass on touched files.
