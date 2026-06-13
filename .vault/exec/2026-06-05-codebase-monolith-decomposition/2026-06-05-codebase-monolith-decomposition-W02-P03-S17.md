---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S17'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S17 - config diagnostics selection

Scope: `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/entrypoints/cli/_config/_google.py`, and config CLI tests.

## Description

- Checked `vaultspec-rag` service health before semantic discovery.
- Ran exact discovery over config auth, diagnostics, and output-language test surfaces.
- Ran semantic discovery for config auth diagnostics command extraction.
- Selected `config auth diagnostics list/show/report` as the next coherent config command group because it is a self-contained sub-noun under `auth_app`, has existing output-language coverage, and delegates domain work to `application.auth`.

## Outcome

Selection completed. RAG ranked `auth_diagnostics_show`, `auth_diagnostics_list`, and adjacent diagnostics payload emission as the highest-confidence extraction candidates.

## Notes

The larger `auth` group remains a later candidate, but diagnostics was the lower-risk residual slice for this step because it does not require relocating the apoderado command tree.
