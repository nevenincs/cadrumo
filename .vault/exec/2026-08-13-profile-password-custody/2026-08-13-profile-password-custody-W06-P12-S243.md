---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:72beed08483331ef4f74ca610953d4ea2e0f87492289c27637059012beda5113'
step_id: 'S243'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Repair Spanish, Catalan, and Hungarian localized reference tokens and generated CLI toctree integration so all localized nitpicky builds resolve current targets

## Scope

- `docs/locales/ and docs/reference/cli/`

## Description

- Trace localized token and generated CLI-reference ownership through semantic discovery and exact source confirmation.
- Restore exact Markdown targets in the Spanish, Catalan, and Hungarian messages reported as inconsistent.
- Replace a stale translated filing paragraph with substantive current-language prose carrying no invented reference.
- Enrol every generated nested CLI group page in its owning family page's hidden toctree.
- Add a graph-derived test proving every generated nested group has one family-toctree entry.
- Run catalogue completeness and drift, PO parsing, generator gates, localized nitpicky builds, Ruff, and formal review.

## Outcome

Spanish, Catalan, and Hungarian builds preserve the exact source reference-token sets for the three failing messages. The CLI generator now places all seventeen nested group pages under their five family landing-page toctrees without hand-editing generated files. Fourteen localization and CLI-reference tests pass, every PO file parses, Ruff passes, isolated coherent-HEAD nitpicky builds pass for all three languages, and formal review approved with no findings.

## Notes

The live shared-tree build is obstructed before documentation parsing by a concurrent Modelo 721 revision split. The localized builds therefore ran against an isolated HEAD snapshot with the S243 files overlaid and only the peer-blocked casilla generator replaced; all passed.

The fresh catalogue-drift gate ran and remains red on fourteen pages whose source/catalogue drift predates and lies outside the three S243 token messages. Catalogue completeness and all S243-owned msgids are green. No generated CLI reference page was edited or committed.
