---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P07.S16` execution record

Extend registry compile-time validator to check manuals cross-references in `src/aeat/domain/calculations/registry/`.

## Action

Modified `_sources.py` and `_legal.py` to enforce compile-time checks:
- Verifying `SourceReference` of kind `manual_pdf` has a valid manifest and structure folder containing `manual.json` and `chapters.json`.
- Verifying `LegalReference` of kind `manual` references a valid section JSON that parses cleanly against the strict schema.

## Verification

Enforced by `RegistryValidator` when executing full validation.
