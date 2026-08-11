---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:d8507c1d70c7ec96cffa5bdf44b711916671c6a1b493bb0662958fffc0b5f3a3'
step_id: 'S01'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Land the NoRecoveryOutcome import fix and prove clean collection

## Scope

- `src/cadrumo/application/modelo/_preconditions.py`

## Description

- Confirm the canonical `NoRecoveryOutcome` import is present at the Modelo precondition boundary.
- Import the production Modelo precondition module and enumerate the live profile catalogue.
- Repair independent collection blockers without restoring deleted private helpers or compatibility aliases.
- Remove a misleading export-identity formatter test and its dead profile-path constants because neither exercised the export boundary.
- Restrict the complexity baseline to live `src/cadrumo` paths measured by the public production scanner.
- Run a repository-wide serial collect-only gate after the repairs.

## Outcome

The canonical import is present and the production module imports successfully. The repository-wide serial collect-only command exits zero with no collection errors. Focused collection-repair tests pass, the live registry verifies 73 modelos and 94 revisions, scoped Ruff and BasedPyright checks are clean, and scoped diff checking reports no whitespace errors.

## Notes

The import itself was already present in committed history when execution resumed. Five independent collection blockers exposed by the first full collection were repaired at their current canonical owners. No fake, mock, stub, monkeypatch, skip, xfail, compatibility facade, or mirrored business logic was introduced. The stale export formatter test was deleted rather than preserving a false behavioral claim.
