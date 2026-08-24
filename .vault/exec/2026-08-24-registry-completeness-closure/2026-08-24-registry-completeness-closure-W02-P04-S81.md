---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:fc70d9cbc83eb856361ff4515bf5dcc7312348eacf77dcedd914d87edfa09d2a'
step_id: 'S81'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Correct Modelo 036 public lifecycle and CLI Sede-only docstrings to state Sede-or-competent-AEAT-office recording, retain optional electronic justificante semantics, and preserve the no-local-filing boundary.

## Scope

- `src/cadrumo/application/modelo/_m036_lifecycle.py`
- `src/cadrumo/entrypoints/cli/_modelo_m036_cli.py`
- `src/cadrumo/application/modelo/tests/`
- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Correct the lifecycle module, command schema, and declaration-recording
  docstrings from Sede-only wording to AEAT Sede-or-competent-AEAT-office
  filing.
- State that `sede_justificante` is optional electronic receipt evidence and
  that a local record command never files with AEAT.
- Correct all three callback docstrings and add focused schema and docstring
  regressions without changing the recording service or CLI behavior.

## Outcome

The owned changes landed in mixed ancestor `b40fd5bf4c` and scoped follow-up
`188eeb0d5b`. The focused contract and CLI tests pass (20 tests), as does Ruff
over the four scoped files. Independent semantic discovery, whole-file review,
and exact-symbol confirmation found one canonical encrypted M036 recording
service with the CLI delegating to it, not a parallel writer or submission path.

## Notes

Rendered CLI help continues to be governed by the separate localized catalogue;
S81 intentionally corrects callback and lifecycle docstrings rather than
creating a second localization authority. The associated independent audit is
`2026-08-24-registry-completeness-closure-s81-post-review-audit`.
