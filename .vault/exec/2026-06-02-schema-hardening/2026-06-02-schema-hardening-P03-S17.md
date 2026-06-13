---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S17'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---




# Verify signed cuota role coverage

## Scope

- `src/aeat/domain/calculations/registry/test_semantic_role.py`

## Description

- Inspect current signed-cuota role names across Modelo 100 and Modelo 200.
- Add a real-registry regression test covering IRPF and IS signed result
  casillas.
- Assert that the stale IS role spelling `resultado_ingresar_o_devolver_is`
  has no committed members.
- Apply the minimal Ruff import-block repair required by the touched test file.

## Outcome

- Modelo 100 carries `resultado_ingresar_o_devolver_irpf` on casilla `0700` for
  revisions `2024` and `2025` only.
- Modelo 200 carries the canonical IS role `is_resultado_ingresar_o_devolver`
  on casilla `DP200014B:00599` for revision `2024-y-siguientes`.
- The older `resultado_ingresar_o_devolver_is` spelling remains retired in the
  committed registry.
- The focused signed-cuota test, Ruff check, plan check, and vault
  body/frontmatter checks passed.
- `P03.S17` is complete.

## Notes

- `src/aeat/domain/calculations/registry/test_semantic_role.py` already had
  formatting-only shared-worktree churn before this slice. The staged diff must
  be reviewed explicitly so the signed-cuota test and Ruff import repair remain
  distinguishable from that pre-existing formatting change.
