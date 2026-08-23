---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:32c56108af7423422c442b2ef57c2a3baeaf76f9977a7717be5ba881f1ef4702'
step_id: 'S16'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Resolve review findings by locking official evidence coordinates and physical counterpart digests

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py`
- `src/cadrumo/tests/fixtures/external_layout_candidates/tests/test_candidate_contract.py`
- `.vault/audit/2026-08-23-issue-620-external-pdf-signal-authority-adjudication-final-review-audit.md`

## Description

- Bind each modelo to its reviewed official-source evidence coordinate.
- Recompute pair-render counterpart digests from the actual adjacent PDF.
- Add focused mutations for valid-looking authority drift and digest drift.
- Record both review findings as resolved and run only the affected gates.

## Outcome

The contract rejects any syntactically valid replacement of the reviewed
official authority, document identity, URL, digest, or complete page mapping.
Physical validation also rejects a valid but incorrect counterpart digest by
hashing the adjacent opposite-kind PDF directly. The focused contract module
passes 40 tests and Ruff reports no violations in the two changed Python files.

## Notes

No live network requests were added and no official PDF bytes were committed.
