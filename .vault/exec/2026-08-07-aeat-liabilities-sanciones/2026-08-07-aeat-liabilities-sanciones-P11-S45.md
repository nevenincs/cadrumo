---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7b557f3f165ec1756c353a86355941165bff36a698f8626aa95c8da232efc656'
step_id: 'S45'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Attach a standing info Notice to the history payload stating it records what AEAT served and is neither a payable balance nor the recaudacion register the deudas verbs read, because payment, appeal, reduction and supersession are not stated on the document, verified by a test asserting the notice is present on every history emit

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`

## Description

- Added the standing informational Notice distinguishing served document figures from a payable balance and the deudas recaudacion register, including empty histories.

## Outcome

Delivered and verified within the Step's declared scope.

## Notes

RAG discovery was attempted first but unavailable because service compute admission was quiesced. Grounding continued from the accepted decisions, existing execution records, source, targeted symbol search, and live CLI behaviour.
