---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3a6b071e9f68c907f43fc9f66b3614ab0242f56ac64d8dfa1f3ee8b447f72013'
step_id: 'S13'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Correct cross-model outcomes to select applicable revisions or refuse current-form alignment

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests/test_external_layout_candidate_matrix.py`

## Description

- Bind Modelo 130 and Modelo 131 candidates to their current authored revisions.
- Bind Modelo 303 candidates to the applicable historical 2025 revision.
- Isolate Modelo 036 and Modelo 349 as explicitly out-of-revision parser exercises.
- Assert every sidecar applicability verdict against canonical registry selection or explicit refusal.

## Outcome

- The matrix cannot represent the historical Modelo 036 and Modelo 349 layouts as current-form verification.
- Exact parser buckets and the zero-fabricated-values guard remain enforced for both candidate variants.
- The focused matrix module and Ruff checks pass, and focused review recorded no findings.

## Notes

- Final verification followed the completed S12 sidecar migration.
