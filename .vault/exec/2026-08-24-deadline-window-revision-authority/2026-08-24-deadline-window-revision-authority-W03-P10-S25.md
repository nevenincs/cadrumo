---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c4ed00d4eb29185bef4d2b5e3224e9421424dbd060309f9cbeb0241a7070fd09'
step_id: 'S25'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Prove qualified resolution wildcard and exact scopes, official-code distinction, ambiguity refusal, and no year borrowing

## Scope

- `src/cadrumo/domain/deadlines/tests/`

## Description

- Discover the canonical qualified resolver and its governing decisions with Vaultspec RAG.
- Reuse the existing projected-window fixture and atomic semantic-coordinate matcher.
- Prove exact official-code identity for `01` and `35` despite their shared rate concept.
- Prove wildcard matching, exact scoped matching, ambiguity refusal, and strict filing-year isolation.
- Run the isolated resolver tests and Ruff against the owned test module.

## Outcome

The resolver proof now distinguishes official M210 codes at the atomic coordinate,
selects both wildcard and exact scopes deterministically, refuses overlapping matches,
and returns absence instead of borrowing following- or future-year windows. All eight
focused tests pass and Ruff reports no violations.

## Notes

Vaultspec RAG located the existing canonical `_resolve_projected_filing_window` and
`deadline_window_semantic_coordinates` path before editing. No production code,
resolver, vocabulary, qualifier mapping, or code list was added or redeclared.
