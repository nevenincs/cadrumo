---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:12c2252f6f4b382e99d3b715c8700106b629eb2f274ca678306a4b0bd62f94fb'
step_id: 'S15'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Prove offset, length, source-anchor, target-revision, and generated-file mutations are detected

## Scope

- `dev/registry/tests/`

## Description

- Add a real-filesystem publication gate covering offset, length, source-anchor, target-revision, and output-byte mutation of a freshly rendered candidate.
- Exercise the production loader, provenance verifier, and atomic publication boundary for every mutation rather than reconstructing layout logic in the test.
- Assert candidate refusal before cutover and byte-identical preservation of both the live export and the revision's non-export authority.
- Run independent review against the accepted generator-authority decision and hard-cut legacy rule.

## Outcome

All five mutation classes fail closed before a journal, backup, or live export change. The independent review found no critical, high, or medium issue and confirmed no legacy reader, merge, copy, or fallback surface was added.

## Notes

Focused generator-authority tests passed 50/50; Ruff, format, and file-scoped BasedPyright passed. No data loss, persistent failure, or Git lock occurred.
