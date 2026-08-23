---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4f9a6c3b144dabdd4e2c8f0972fcf7ebaebd20c1d83ad8091a2ae03cd39ce758'
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
