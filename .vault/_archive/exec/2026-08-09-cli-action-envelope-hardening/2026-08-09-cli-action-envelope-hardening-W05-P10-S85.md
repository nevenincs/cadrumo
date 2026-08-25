---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f734737a477bac4d63a0a676aca27568bb4a40d55b74266b12e2ee933695007b'
step_id: 'S85'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate taxpayer-domain recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/domain/contribuyente`

## Description

- Audit the taxpayer domain for recovery producers carrying prose or an unresolved recovery.

## Outcome

- The declared package raises no registered error at all: it is a pure modelling surface whose invariants are enforced by its typed models rather than by refusal producers.
- There is consequently no recovery producer to migrate, and the step's contract is satisfied by construction rather than by prior migration.
- Structural verification: the audit is a scan of the declared package.

## Notes

- Closed as already satisfied. Recording the reason matters here because the absence is structural: a later reader should not expect producers to appear in this package, since refusals for taxpayer facts are raised by the application services that consume the models, not by the models themselves.
- No carry-forward.
