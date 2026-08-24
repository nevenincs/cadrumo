---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:360de1e258ab90e14f13ef3609613d9c2f189806f6a90eb8f9ebf69b2d2babdd'
step_id: 'S03'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---




# Define the canonical deadline semantic coordinate from modelo, Period, ResultDisposition, and official tipo-renta code scope using existing period authorities

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Description

- Add one immutable semantic-coordinate projection for deadline law facts.
- Derive filing-year and token identity from `Period` and reuse `registry_period_kind`
  as the sole registry-token cadence authority.
- Project only `ResultDisposition` and validated official tipo-renta scope as
  qualifiers, normalizing the set-like official-code scope.
- Export the projection through the calculations-registry facade and cover its
  identity boundaries with focused unit tests.

## Outcome

Deadline validation and canonical authority projection now have one reusable identity
for `(modelo, filing year, period token, resultado scope, tipo-renta scope)`. Authored
ids, revision ids, dates, and cadence labels cannot manufacture a distinct semantic
fact, and no arbitrary qualifier map is admitted.

## Notes

The first focused pytest invocation encountered an xdist worker crash. A serial rerun
exposed a missing test classification marker; after adding the repository-required
unit and hex-domain markers, all eight focused qualifier and coordinate tests passed.
