---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:670f378d6ce49f6b57b6393e882c1f3b1368ad38a951bebcd6c2da4f9b3fc2b9'
step_id: 'S03'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Prove the intermediate representation consumes shipped parser output and never extracted derivatives

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Copy the catalogue-selected, SHA-verified official Modelo 200/2025 binary into two isolated filesystem roots.
- Materialise contradictory `.extracted.md` and `.extracted.json` review derivatives beside each exact binary before loading the intermediate representation.
- Prove the two intermediate representations are equal, omit both derivative sentinels, and retain every sheet and field from the shipped parser output.
- Run independent review of source selection, parser projection, derivative exclusion, and test-integrity constraints.

## Outcome

The intermediate representation is now protected by a real-binary, anti-vacuity proof. It resolves each copy through the verified source catalogue before parsing, and neither derivative sibling can affect coordinates or appear in the intermediate representation.

Focused verification passed: the dedicated S03 test passed, the existing S02 plus S03 IR tests passed together, Ruff passed, and BasedPyright reported zero errors, warnings, and notes. Independent review recorded no findings.

## Notes

The shared standard Git index remains deliberately untouched because it still presents the already-pushed S02 paths from a stale index state. S03 delivery uses a separate initialized private alternate index if the shared lock persists; no shared lock file is changed.
