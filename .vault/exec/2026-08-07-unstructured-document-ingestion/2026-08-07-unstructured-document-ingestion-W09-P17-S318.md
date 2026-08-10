---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:656eab0efe01eb5e3182d3c9d83fcf72f4e8c9e9d8ee181031a01cb46016124b'
step_id: 'S318'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Funnel the wizard save-exit notice through the shared output boundary, matching the sibling emitter in the same module that already does

## Scope

- `src/cadrumo/application/wizard`

## Description

- Confirm the row's premise at HEAD before acting, since a peer had already funnelled the emitter.
- Consolidate rather than accept the redeclaration the funnelling introduced.
- Let the gate red first, and update its allow-list only after reading what it caught.

## Outcome

The save-and-exit disclosure now reaches the operator through the module's output boundary. **It already did when this row was picked up** — a peer had funnelled it — **but it had been given its own renderer call, its own sandbox-banner prepend and its own echo, duplicating the pair its sibling in the same module already held.**

That is the same redeclaration the streamed-progress fix made one package over: routing through the same renderer is not the same as sharing one implementation. **Two private copies of a boundary is precisely how one of these two emitters came to bypass it while the other did not** — the module had already run that experiment.

Both now delegate to one writer. The module holds one renderer call and one echo.

## Verification

    module renderer call sites      1
    module echo sites               1
    output-surface gate             6 passed
    lint and format                 clean

**The gate reddened before the allow-list was updated, on both of its properties at once** — flagging the new shared writer as an unowned emit site, and flagging both old exemptions as stale because neither function echoes any more. That is the second time in this session those rules have bitten on a real change rather than a synthetic control.

## Notes

**The allow-list shrank from two entries to one**, which is the structural result: the property is now enforced by there being a single writer rather than by two audited exceptions.

**One process defect, disclosed.** The first consolidation attempt removed the wrong import block — the new helper's own imports rather than the now-dead sibling ones — leaving four undefined names. The lint gate caught it immediately and it never reached a commit. The cause was a byte-level pattern matched against a file with mixed line endings, where the two candidate blocks differ only in their surrounding context.
