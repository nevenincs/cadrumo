---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S2349'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---




# W85.P414.S2349 Modelo 036 lifecycle verbs registered

## Scope

- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Registered the Modelo 036 declarative-recording verbs (`alta`, `modificacion`, `baja`) under `aeat app modelo m036` in `src/aeat/entrypoints/cli/_modelo.py`.
- Verbs delegate to `record_m036_declaration` (landed in commit 2 of the M036 3-commit landing plan); the service persists the typed `M036DeclarationResult` via `SecureSnapshotRepository` against `LIVE_M036_DECLARATION_NAMESPACE` and emits the matching `BucketEventType.CENSO_DECLARATION_{ALTA,MODIFICACION,BAJA}` event into the active bucket history.
- Result envelope rendered via `_emit_envelope` against the newly-registered `M036DeclarationRecordResult` payload schema (registered under three keys: `modelo.m036.alta`, `modelo.m036.modificacion`, `modelo.m036.baja`).
- Locale keys translated across all four catalogues (en, es, ca, hu) per the `aeat-locales-cli` rule.

## Outcome

- S2349 closed by commit `6ac0cd692 feat(m036): aeat app modelo m036 {alta,modificacion,baja} CLI verbs + 4-locale keys + 10 shape tests (M036 commit 3/3 — landing plan complete)`.
- 10 CLI shape tests pass; 39 M036-related tests pass across contracts, service, and CLI layers.
- The local app never files at AEAT per the 2026-05-16 ADR amendment; these verbs only record what the operator filed at sede.

## Notes

- Landed end-to-end via the ADR-driven 3-commit landing plan: precondition bundle (commit 1) -> service implementation (commit 2) -> CLI verb mount + locales + shape tests (commit 3).

