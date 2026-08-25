---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a6c853d9a7fb445443d1bbc95106bd1cdfe91d42fc0c7b47584c39401427d813'
step_id: 'S124'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Centralize Google adapter terminal-verdict construction

## Scope

- `src/cadrumo/application/operator_actions/_preconditions.py`
- `src/cadrumo/adapters/outbound/google/_preconditions.py`
- Google adapter modules and structural tests

## Description

Moved generic fact-only terminal-verdict construction to the application-owned operator-actions package and made Google modules delegate condition facts and outcome policy through one attachment helper.

## Outcome

- `no_action_precondition_verdict` is the sole generic application constructor used by Google.
- Google `_preconditions.py` only clones and attaches outbound-storage errors; it does not redeclare the verdict record.
- VaultSpec RAG located the semantic duplication and a whole-Google exact-symbol scan confirms zero direct `ConditionEvidence` or `PreconditionVerdict` constructors in production modules.
- The structural gate scans every top-level Google module, including `_preconditions.py`, and rejects future local construction.
- Verification: focused helper/structure tests — 2 passed; broader S123 non-registry suite — 21 passed; ruff clean.
- Independent review: PASS.

## Notes

Campaign-wide pre-existing fact-only builders remain explicitly assigned to open deduplication step `S125`.
