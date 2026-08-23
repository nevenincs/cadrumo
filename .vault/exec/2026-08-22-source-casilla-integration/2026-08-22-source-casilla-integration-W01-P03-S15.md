---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:53c53246abdc532258fc48f3cca43e33080eb9b2ccabbc859617f908d8e91eb1'
step_id: 'S15'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# emit lexical destination matches as advisory findings only

## Scope

- `dev/source_connectivity/discovery.py`

## Description

- Tokenize capability evidence and authored casilla semantic metadata without numeric identifiers.
- Emit deterministic overlap records carrying an immutable `advisory_only=True` marker.
- Require substantial capability-token coverage and never expose an authoring or binding mutation path.

## Outcome

Lexical proximity is now visible for investigation while remaining structurally incapable of authoring a binding or claiming legal equivalence. The report preserves modelo, revision, canonical casilla id, capability locator, and exact shared tokens.

## Notes

The first corpus pass exposed a missing required Spanish Modelo 210 translation. Discovery now reads authored localization keys, semantic roles, and sections, leaving the localization refusal intact. Ruff passed; the live advisory scan retained amortization candidates while marking every row report-only.
