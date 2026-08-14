---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:be29445a2b1e841d798b474350e205551c77e927fa0908a1ae3dd5563509911b'
step_id: 'S62'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize the M130 committed registry snapshot family

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Description

- Replace three identical M130 committed-snapshot fixtures with one registry-test conftest owner.
- Preserve function scope, non-autouse behavior, registry authority dependency, and snapshot lifecycle.
- Keep the M180 and M100 snapshot families local and unchanged.

## Outcome

All three formula-runtime modules now resolve `committed_modelo_130_snapshot` from their narrowest common conftest. The M130 family has one definition, while other modelo and revision families remain independently owned.

## Notes

All 32 focused tests collect, fixture discovery and function cadence are correct, and seven behavior tests pass. Twenty-five setup cases are blocked by concurrent registry authority data loading M130 and M180 revisions as `pending_review`; the unchanged snapshot helper correctly refuses filing-grade use. Ruff, diff integrity, family isolation, and independent review passed. The ownership manifest will refresh atomically after the remaining registry fixture families to avoid repeated full-tree census cost.
