---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:02cb37083e03d9a56ebaf49996fec235e606e52babc0655e42d9125a5349d6ff'
step_id: 'S39'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Project the comparecencia refusal, the unparsed-document report and the re-fetch no-op through the typed Notice channel on the shared envelope spine, rebuilding each text line from the same notice so JSON and text cannot drift, verified by test_rule_surface_conformance

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_notifications_cli.py`

## Description

- Projected comparecencia, idempotency, and parse-refusal diagnostics through shared typed Notice values for JSON and text.

## Outcome

Delivered and verified within the Step's declared scope.

## Notes

RAG discovery was attempted first but unavailable because service compute admission was quiesced. Grounding continued from the accepted decisions, existing execution records, source, targeted symbol search, and live CLI behaviour.
