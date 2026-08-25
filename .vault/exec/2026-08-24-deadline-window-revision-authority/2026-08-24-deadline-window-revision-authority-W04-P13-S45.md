---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:02a3a7f72724ec16de81dd0bcfaa49c9c45dce836124bbeb3a450a729fd832ce'
step_id: 'S45'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Make deadline reference-date semantics canonical and deterministic. Correct stale date.today() documentation, replace direct wall-clock reads in deadline-path tests with explicit or frozen today_madrid() input, and derive exercised filing years from the supported-filing-year catalogue while preserving literal official dates only in source-fidelity tests

## Scope

- `src/cadrumo/domain/deadlines/`
- `src/cadrumo/entrypoints/cli/tests/`
- `.vault/audit/`

## Description

- Correct deadline API documentation to name the canonical Europe/Madrid civil-date default.
- Derive the M130 CLI behavior-test year from `catalogues.supported_filing_years` and its revision through `select_revision`.
- Derive an explicit reference date between consecutive registry close dates and freeze the existing `frozen_clock` seam so `today_madrid()` is deterministic.
- Preserve registry-owned close dates as resolved facts rather than copying them into behavioral assertions.

## Outcome

Deadline reference-date behavior is deterministic and authority-driven. The real CLI overdue and in-time branches run under one explicit Madrid civil date derived relationally from canonical M130 windows; neither branch depends on the execution day or a copied supported-year horizon. Production behavior remains unchanged and continues to default through `today_madrid()`.

## Notes

Vaultspec RAG discovery was attempted first as required. The running service refused the search because its 0.4.1 release differed from the 0.4.2 client; direct local fallback was unavailable while that service held the index. Exact-symbol searches then confirmed the scoped clock and catalogue call sites. Focused Ruff and formatting checks passed. The real CLI integration module passed all three tests.
