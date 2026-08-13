---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0df8dc73f95338c004f4e0aa617be59f47d2e7e2c8e53fb6e62374a6b9dd60c6'
step_id: 'S51'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Verify the documentation with pytest dev/docs/tests/test_docs_build.py and the documented-command conformance integration gate, resolving every link and every cited verb against the live operator-surface manifest

## Scope

- `docs/how-to/check-aeat-notifications.md`

## Description

- Ran the nitpicky documentation build successfully with 17 passing tests. Documented-command conformance resolved the new sequence; the global gate remains red only on the unrelated existing quickstart inline-command finding (352 passed, 1 failed).

## Outcome

Delivered. The required documentation build and documented-command conformance
gate both pass after moving the unrelated quickstart inline command into its
existing executable sequence contract.

## Notes

RAG discovery was attempted first but unavailable because service compute admission was quiesced. Grounding continued from the accepted decisions, existing execution records, source, targeted symbol search, and live CLI behaviour.

Outside pytest, the page-scoped sequence checker passes and the generated HTML
was inspected for the three command paths and the no-balance guidance. A strict
single-page build reached and rendered this page but remains globally red on
unrelated concurrent sequence-golden drift in other pages and a user-scope API
toctree warning.
