---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:38ad2016d6de8b38f33d5623f524a43953ed887348efbb449ed88c039ea03750'
step_id: 'S07'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Enforce exact-one deadline ownership through canonical select_revision including period-sensitive cutovers

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Resolve every deadline filing coordinate through the canonical `select_revision` authority.
- Reject a deadline nested beneath any revision other than the law-selected owner.
- Accumulate no-owner and ambiguous-owner failures through the registry validator contract.
- Exercise the rule with an isolated same-year, period-sensitive revision cutover.
- Route the ownership invariant through `RegistryValidator` before authority construction.

## Outcome

Deadline rows now carry an exact-one revision-ownership invariant at registry build.
The containing revision is asserted only after selection from the window's canonical
`Period` coordinate, so it cannot influence the selection. Focused ownership,
uniqueness, and temporal tests passed, as did Ruff on every modified Python file.

## Notes

The bundled corpus is intentionally not asserted green in this step: the duplicate and
non-owner rows inventoried by the campaign remain until the approved corpus-repair
steps. Isolated fixtures prove this invariant independently of those known failures.
