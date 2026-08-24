---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0257fbab2d14ebf9a0bf8bf203b38fd3102d0ec2ca5a517e495a0911467e580d'
step_id: 'S23'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Extend resolve_filing_window with optional ResultDisposition and official tipo-code context using one exact matcher and ambiguity refusal

## Scope

- `src/cadrumo/domain/deadlines/_plazo.py`

## Description

- Discover resolver and matcher implementations with Vaultspec RAG before editing.
- Extend `resolve_filing_window` with optional canonical resultado and official-code context.
- Reuse the registry's atomic semantic-coordinate projection for wildcard and exact matching.
- Refuse multiple matches with `DeadlineValidationError` and reserve `None` for zero matches.
- Add isolated, bite-capable resolution tests without mocks or parallel code vocabularies.

## Outcome

`resolve_filing_window` remains the single public filing-window resolver and now
supports post-calculation qualifier context. The implementation delegates match
semantics to `deadline_semantic_coordinate` and
`deadline_window_semantic_coordinates`; it defines no second resolver, matcher,
period parser, enum, or tipo-code map. A deferred public-facade import preserves
the existing registry/deadline initialization boundary.

Focused Ruff and six resolver tests pass, including planted malformed-context
refusals at the public boundary. The adjacent overview delegation suite
collects successfully and passes seven non-registry cases; four bundled-authority
cases remain blocked by concurrent, pre-existing incomplete deadline evidence for
Modelo 303 revision 2023 and Modelo 322 revision 2008-2022.

## Notes

The first integration run detected a circular import when the public registry
facade was imported at deadline-module initialization. Moving that same facade
import to resolution time removed the cycle without importing private registry
modules. No data was changed or lost.
