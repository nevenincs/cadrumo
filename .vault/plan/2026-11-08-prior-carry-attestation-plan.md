---
tags:
  - '#plan'
  - '#prior-carry-attestation'
date: '2026-11-08'
tier: L1
related:
  - '[[2026-11-08-prior-carry-attestation-adr]]'
modified: '2026-11-08'
body_schema: body-v2
body_hash: 'sha256:45fd8807e1e9b881277b5888fa656c33d3a1bfea663bcd15e012b2c921865285'
---

# `prior-carry-attestation` plan

## Description

Approved 2026-11-08. Basis: the coordinator's ruling of 2026-11-08 on APP-QA D33, which chose the served form action over a profile fact and directed that it be recorded and implemented.

Implement `2026-11-08-prior-carry-attestation-adr` for the four Modelo 100 earlier-ejercicio carries. That ADR governs every Step and cites `2026-11-08-prior-carry-attestation-reference` for the code trace. It amends `2026-08-24-modelo-edit-contract-adr` D4 by one binding intent kind. Work happens in the BACKEND-RENTA worktree on branch `renta/d33-m100-carry` and lands through LANDER.

## Steps

- [x] `S01` - Record an attested zero on the operator layer and admit the attest_no_amount binding intent; `src/cadrumo/domain/modelos/calculation_revision_operator_layer.py`.
- [x] `S02` - Resolve an attested carry as attested by the filer and raise the disagreement when a stored earlier return differs; `src/cadrumo/application/calculations/multi_year.py`.
- [x] `S03` - Serve the per-declaration attestation action with its words and addresses on the work form; `src/cadrumo/application/modelo/work_form.py`.
- [x] `S04` - Render the served action in the window and stage one attest intent per address; `native/desktop/frontend/src/components/modelo/form/session.ts`.
- [x] `S05` - Regenerate the operation contract manifest and wire types and prove every envelope year; `native/desktop/frontend/src/shell/modeloContract`.

## Parallelization

## Verification
