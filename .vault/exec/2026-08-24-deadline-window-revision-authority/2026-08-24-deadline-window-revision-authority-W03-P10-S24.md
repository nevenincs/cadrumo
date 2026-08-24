---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bf16104f6d8c1c7efa37a08dfaf27724fddb4054d63449a77b2e229c84323f80'
step_id: 'S24'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Keep resolve_filing_closes_on as the unqualified convenience and route post-calculation M210 plazo through the same matcher

## Scope

- `src/cadrumo/domain/deadlines/_plazo.py`

## Description

- Search the code and decision corpora with Vaultspec RAG for pre- and post-calculation plazo matching paths.
- Read the canonical resolver and pre-calculation work-plazo consumer in full, then confirm every resolver call site by exact-symbol search.
- Preserve `resolve_filing_closes_on` as the qualifier-free convenience over `resolve_filing_window` and document the shared-matcher boundary explicitly.
- Run focused Ruff and pytest gates across the deadline resolver and work-plazo contract.

## Outcome

The redeclaration audit found no competing M210 deadline resolver. The pre-calculation work posture calls `resolve_filing_closes_on`, which delegates directly to `resolve_filing_window`; qualified post-calculation callers can pass canonical `ResultDisposition` and official tipo-renta context to that same entry point. The public contract now states this ownership explicitly, preventing the future Notice projection from introducing a second matcher.

Focused Ruff passed. Focused pytest passed with 11 tests.

Independent review passed with no findings and reconfirmed by Vaultspec RAG plus exact-symbol search that the codebase owns one public resolver and one internal matcher.

## Notes

The actual M210 result/tipo inputs and typed Notice emission remain assigned to `W03.P11.S27`; this Step deliberately does not pre-empt that application wiring or create a resolver-shaped wrapper. A later reviewer rerun reached 11 passes and 11 unrelated failures because concurrent Modelo 303 and Modelo 322 registry edits failed authority-grade validation before resolver assertions; the isolated focused run above completed before those shared-tree edits and passed fully.
