---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:eb7acc69bb8057cdd6a72de1b8cf0cd3c3385c09ba17202e9aa7b01f94182c19'
step_id: 'S27'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---




# Route calculated M210 ResultDisposition and official tipo code into canonical deadline resolution and the existing typed Notice channel

## Scope

- `src/cadrumo/application/modelo/`

## Description

- Discover the existing calculation envelope, result-disposition resolver,
  persisted official tipo-renta code, deadline matcher, and typed notice channel
  with Vaultspec RAG, then confirm their exact call sites and uniqueness.
- Add one application projection that resolves M210 plazo only after calculation
  through `resolve_modelo_result_disposition` and `resolve_filing_window`.
- Carry the resulting information notice on the calculate service result and
  append the same projection to calculate and verify envelopes.
- Exercise the projection through the real persisted annual grouped-renta
  calculation path and run focused Ruff and pytest verification.

## Outcome

Calculated M210 resultado and the revision's persisted official two-digit
tipo-renta code now select the canonical registry window and emit one typed
information notice carrying the exact registry window identity, dates, and
grounding references. A missing qualified window emits nothing, preserving the
fetch-gated tipo-28 refusal to invent an offset. The existing unqualified
`modelo_work_deadline_posture` path was not changed.

Vaultspec RAG and an exact production-symbol sweep found one result enum, one
official-code projection, and one filing-window matcher. The overview's
`_resolve_filing_window` name is an import alias of that public matcher, not a
second implementation; the observation `ResultDispositionProjection` is a
provenance record, not a replacement vocabulary.

## Notes

- Production and focused-test changes were captured in peer commit
  `68d37acc7e` alongside concurrent operations work.
- Focused Ruff passed for every touched application, CLI, and test module.
- The real M210 grouped-renta test passed: `1 passed in 52.81s`.
- Broad corpus gates were intentionally not run for this step; they are owned by
  later plan closure steps and concurrent registry corpus work.

