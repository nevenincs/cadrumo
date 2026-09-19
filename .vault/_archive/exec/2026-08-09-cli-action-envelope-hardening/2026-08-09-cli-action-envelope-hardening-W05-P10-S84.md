---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5dca724d749c0342cac5930149c338b4bafc5211592d8b82a0a55c87c452e6bc'
step_id: 'S84'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Replace calculation-domain applicability, query, authority-grade, and loader-race command/retry prose with domain-owned failed-condition facts and boundary-resolved typed outcomes

## Scope

- `src/cadrumo/domain/calculations/_errors.py`
- `src/cadrumo/domain/calculations/_applicability.py`
- `src/cadrumo/domain/calculations/_applicability_modelo202.py`
- `src/cadrumo/domain/calculations/_queries.py`
- `src/cadrumo/domain/calculations/_snapshot.py`
- `src/cadrumo/domain/calculations/_loader.py`
- `src/cadrumo/domain/calculations/_loader_cache.py`
- `src/cadrumo/domain/calculations/_loader_fingerprints.py`
- `src/cadrumo/domain/calculations/tests`
- `src/cadrumo/application/calculations`
- `src/cadrumo/entrypoints/cli`

## Description

- Replace applicability, query, snapshot, authority-grade, and concurrent-tree command/retry prose with closed domain conditions and facts.
- Resolve profile cases to existing canonical actions and invariant/authority cases to explicit SAFETY no-action outcomes in the application layer.
- Attach the typed projection at the shared CLI boundary and prove the domain remains application-import-free.

## Outcome

Commit `43feeeb42f` and producer-proof commit `a48f62af95` establish 15 direct typed classification producers across the scoped registry surfaces. Application resolution exhaustively handles every closed condition; no retired command/retry directive remains.

Twenty-one focused tests pass, including real query and layout producer assertions and exact forbidden-fragment mutations. VaultSpec RAG and independent review found no action, verdict, or error-code authority redeclaration.

## Notes

- `43feeeb42f` was created by a concurrent shared-index commit and also contains four substantive test files from other owners. This provenance is disclosed; shared history and those owners' work were not rewritten or rehomed.
- Two broader cache-isolation failures belong to current cache fixtures and do not execute the S84 typed-outcome contract.
