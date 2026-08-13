---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:73d76b58a9ccc9cc0f30baa0054272f5eca8cb4bc66ad92727f555c3f3e84bde'
step_id: 'S48'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---




# Add the cli-sequence contract file for the notification-document reads declaring the document pull, document view and document history steps in singular imperative sentences, each blocked live-aeat where it reads the operator's authenticated session

## Scope

- `docs/_sequences/contracts/how-to/check-aeat-notifications/check-notifications-documents.seq`

## Description

- Added the three-step CLI sequence for pull, local view, and local history, marking only the authenticated pull as live AEAT.

## Outcome

Delivered and verified within the Step's declared scope.

## Notes

RAG discovery was attempted first but unavailable because service compute admission was quiesced. Grounding continued from the accepted decisions, existing execution records, source, targeted symbol search, and live CLI behaviour.

Manual documentation rendering found that the local view and history static
frames also require explicit blocker reasons. Both now declare
`credential-store`, while pull alone declares `live-aeat`; the page-scoped
sequence checker is clean.
