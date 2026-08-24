---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:9ead8081c9d0e7e785c2bd3fa613d3f058de01e004be2152c0a8f3ff5fd10384'
step_id: 'S05'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Enforce equality between deadline filing_year and Period.filing_year while preserving following-calendar-year physical dates

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Enforce one tax-year identity between each deadline's redundant `filing_year` and canonical `Period`.
- Prove following-calendar-year physical filing dates remain valid and do not redefine that identity.
- Reject a planted mismatch at the schema's single hydration boundary.

## Outcome

`DeadlineWindowDefinition` now fails closed when its authored year differs from the
year embedded in its typed period. Focused schema tests and Ruff pass.

## Notes

The broader deadline-window test selection also loads the committed registry and now
correctly exposes the known Modelo 190 mismatch. Its corpus repair belongs to planned
Step S10 (and Modelo 193 to S11), so this validator Step does not mask or rewrite those
facts.

Concurrent shared-worktree commit `0e535a3919` captured the schema and regression files
while this Step was running. The Step-closing commit therefore records provenance and
plan state without reverting or duplicating those already-committed edits.
