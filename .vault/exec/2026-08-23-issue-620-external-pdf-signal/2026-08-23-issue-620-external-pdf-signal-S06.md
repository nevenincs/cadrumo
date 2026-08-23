---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:cbffdd226f9a77591fd95b8cf5996cfbcced594f745b2d943117029e6802b9a5'
step_id: 'S06'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Implement typed source classification and physical-byte validation for external layout candidates

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/`

## Description

- Add strict frozen typed models for candidate identity, retrieval chain, content address, PDF properties, mutable DocInfo observations, identity scans and limitations.
- Bind the closed five-modelo by two-variant matrix to its directory and filename grammar.
- Recompute digest, size, PDF version, page geometry, encryption, AcroForm counts, DocInfo and extracted-text observations from every committed byte stream.
- Keep `third_party_hosted_external_layout_candidate` outside both the recognised fixture-provenance set and `aeat_published_facsimile`.
- Prove the physical gate bites after a real copied PDF byte stream is changed.

## Outcome

Implementation commit `c98f334880` carries the typed contract and its focused gate. The contract admits exactly ten candidates, preserves `authority_status = unverified`, and makes no change to `RECOGNISED_FIXTURE_PROVENANCES`.

`ruff check` passed over the two S06 Python files. The focused module passed sequentially with 24 tests. A scoped code-review pass found no critical, high, medium or low issue against the accepted external-evidence boundary.

## Notes

The first focused pytest launch used the repository default parallel workers and failed inside xdist before executing a test on the shared drive. The required sequential rerun passed. While validation was in progress, a concurrent broad commit captured the two S06 source files together with unrelated peer work; shared history was not rewritten, and this record names that implementation commit transparently. No data was lost and no mock, skip or xfail was used.
