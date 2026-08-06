---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:4c6a4e16c963535b1f9afed407a7c83c1583ebcbb68a4cf52d475d4299a6835d'
step_id: 'S13'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Freeze the application-edge ceiling at 199

## Scope

- `src/cadrumo/tests/test_importlinter_ledger.py`

## Description

- Lower `_APPLICATION_TO_ADAPTERS_BASELINE` from the obsolete 840 ceiling to the reconciled live count of 199.
- Replace the historical increment note with the durable decrease-only ratchet policy.
- Preserve the source-wildcard and domain-edge ceilings for their separately planned steps.

## Outcome

The imported ledger helper parses 265 configured edges and 229 layered edges. Exactly 199 layered application-to-adapter edges now meet the 199 ceiling, so any new edge fails the ratchet.

`ruff check` passed. The focused ledger module passed all four tests. A fresh uncached Import Linter run analyzed 3,421 files and 16,157 dependencies with all five contracts kept and none broken.

## Notes

No incidents or skipped verification.
