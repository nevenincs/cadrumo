---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a8f93ad17f41e51d6be7e060e82429bf2e8b1de4671a4bced36668c70018c1fa'
step_id: 'S06'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Enforce globally unique deadline IDs and semantic coordinates across every revision with independent bite tests

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Extend the existing modelo-level registry validation pipeline with one global deadline-identity pass.
- Reuse `deadline_window_semantic_coordinates` to compare atomic qualifier coordinates without duplicating matching rules.
- Add independent mutation fixtures for repeated IDs, wildcard-qualified overlap, accepted disjoint qualifiers, and validator wiring.
- Run focused unit tests and Ruff over every touched production and test module.

## Outcome

Deadline-window IDs and atomic semantic coordinates now have exactly one owner across all revisions of a modelo. The focused suite passes four registry-identity tests, and the pre-repair bundled Modelo 303 corpus fails the cold validator with concrete duplicate-ID and duplicate-coordinate diagnostics as intended.

## Notes

The fingerprint-certified warm authority path still admits the previously certified corpus; the approved S09 step owns proof and repair of cold-versus-warm verdict behavior. Data-repair steps later in the plan own removal of the duplicate bundled declarations, so this step does not add an exemption or suppress the expected red state.
