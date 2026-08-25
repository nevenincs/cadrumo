---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:632a29fb2264cc7a53302bf0842357e3c93172645b939eb4298f3b3e9b27e5af'
step_id: 'S75'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---




# Migrate filing continuation producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/filing`

## Description

- Remove the unused bespoke calculation next-action and repair-hint carrier.
- Route operator-reachable filing refusals through the registered application terminal transport and explicit typed no-action conditions.
- Preserve established builder, import, and export catch families.
- Exhaustively partition authored filing-error modules into reachable transports or grounded structural exclusions.

## Outcome

Shared commit `8e532475a4` and proof commit `3695a9a4a8` remove the five legacy continuation candidates and establish canonical fact-only operator-decision outcomes. Seven reachable module families use `ModeloApplicationError`; exactly six renderer/export modules are structurally excluded with downstream owner rationale.

The combined focused suite passes 24 tests, including 14 exhaustive refusal-census proofs. VaultSpec RAG and independent review found no error-code, action, or verdict redeclaration; Ruff and diff checks pass.

## Notes

- The producer migration intentionally invalidates five earlier census rows; S46 and S47 are reopened for final current-tree reconciliation.
