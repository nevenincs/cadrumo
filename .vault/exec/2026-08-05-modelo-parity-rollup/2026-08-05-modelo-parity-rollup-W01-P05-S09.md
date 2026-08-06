---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3c8a24575e9d14eff3f575a803a7576bbeef5e369e360a53e975b669a7920c4b'
step_id: 'S09'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
## Description

- Re-run RAG against the registry authority, validator, formula-reference, and construct-evidence paths.
- Exercise the public validated-authority flow with an invalid formula source reference.
- Exercise construct-evidence projection with incomplete source references and preserve the `unresolved` status.
- Run the focused real-authority tests and static gates.

## Outcome

S09 is complete. No production behavior change was required: the existing registry authority already rejects invalid source references, while the existing construct evidence ledger explicitly reports incomplete references as `unresolved`.

Validation completed with 2 focused tests passing, Ruff clean, Ruff format clean, basedpyright clean, and `git diff --check` clean for the owned test path. The pre-existing S05 changes in `src/cadrumo/domain/calculations/registry/_validate.py` were preserved and not broadened.

## Notes

The proof is intentionally bounded to the authority and evidence-classification axes. It does not claim that every model construct has complete legal or source grounding; that remains measured by the five-domain parity matrix.
