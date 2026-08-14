---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e6cd16b6006aa948a46bf9db08d1136dd686890b80bcbcb7a1d2c6d4cd4105fb'
step_id: 'S87'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Replace Modelo 390 revision 2010-y-siguientes with disjoint source-grounded 2022, 2023, 2024, and 2025 revisions. Select only each year own record design, cap the 2025 source at 2025-12-31, confine RDL 4/2024 article 1 to 2024, preserve proven identities and continuity, delete the open compatibility revision, and prove 2010-2021 and 2026 refuse until exact authority is enrolled

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/390/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Replace the open Modelo 390 revision with exact `2022`, `2023`, `2024`, and `2025` annual epochs.
- Bind every epoch and nested record to its own record-design source and same-year deadline window.
- Cap the 2025 layout authority, confine RDL 4/2024 article 1 to 2024, and retire the 2026 publication exception.
- Add direct selector, source-isolation, legal-scope, unsupported-year, and no-compatibility regression proof.

## Outcome

The validated registry loads with four disjoint Modelo 390 revisions. Each
revision carries one exact filing year and one own-year design source; 2010
through 2021 and 2026 have no candidate. Canonical casilla, binding, formula,
relation, and construct identities remain stable across the source-grounded
epochs.

## Notes

Semantic discovery was degraded because the configured endpoint returned HTTP
500 from a non-RAG service; grounding continued through full source reads and
targeted symbol searches. The focused epoch and directory-loader lane passed 21
tests; the broader calculation lane remains intentionally blocked at the
filing-grade legal-review gate owned by S88-S91. No operator attestation was
written by this step.

## Forward correction

The first generated-tree integration run after the annual epochs landed exposed
two loader assumptions that contradicted the canonical generator output. The
generator owns exactly `export/_generation.provenance.json`, while the loader
previously refused every non-TOML file below a revision. The generator's
`export/` directory also owns the `export_layouts` schema section, while the
generic fragment merger previously required directory and section names to be
identical.

The loader now admits only the exact direct generator-owned provenance file and
maps only the canonical `export/` directory to `export_layouts`. Unknown JSON,
wrong-suffix files, misplaced provenance files, and every other section-name
mismatch remain fail-closed. A real renderer-to-filesystem-to-loader test proves
the generated tree loads and a neighboring unknown JSON file still refuses.

The correction adopts the already-present fail-closed loader-topology package as
a necessary coherent prerequisite rather than silently absorbing it. That
package makes discovery and direct loading enforce the same flat legal tree,
modelo root, revision root, direct section-fragment, canonical filename, unique
administrative-prefix, and folder-owned-section contracts. Dedicated bite tests
now cover every adopted refusal boundary, including direct legal-parameters
loading. The S86 inspection changes sharing the generator test file remain
outside this step.
