---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S0837'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---




# Delegate currency normalization layer execution to centralized backend services

## Scope

- `src/aeat/entrypoints/cli`

## Description

Architecture-decision-superseded. The currency normalization layer is not an operator-facing command; it is a domain service consumed by ledger ingest and transactions processing. There is no `aeat config currency` or `aeat app currency` verb, and there is no operator workflow that would benefit from one — currency normalization happens automatically as part of transaction ingest. The CLI-thin-exposure Steps in W28.P140 would create operator surface area that has no operator use case. Closing as architecture-decision-superseded rather than authoring unused CLI verbs.

## Outcome

Closed as structural evidence; see Description above.

## Notes

No additional code change authored by this record.
