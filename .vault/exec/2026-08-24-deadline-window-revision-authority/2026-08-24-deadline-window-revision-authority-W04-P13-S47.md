---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8c5297999b189d8d6cb100d1a4a140986375aca57580935d992eaf80ef2da124'
step_id: 'S47'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Restore canonical formatting on the shared registry authority after concurrent capture work introduced mixed line endings, then rerun focused authority Ruff, format, and deadline ownership tests without changing behavior

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Reformat the canonical registry authority with the repository-owned Ruff formatter after concurrent authority-capture work introduced mixed line endings and overlong imports.
- Preserve every symbol, comment, and behavior while wrapping only the two affected imports.
- Re-run canonical deadline ownership and native-authority capture tests.
- Obtain an independent formatting-only architecture review.

## Outcome

Ruff check and format check pass. The focused registry authority, native-capture, deadline ownership, and projection suite passes 21 tests. Independent review approved with zero findings and confirmed the final diff is formatting-only: two imports wrapped, with symbol and comment identity preserved.

## Notes

The first review correctly rejected an unstable intermediate tree because a peer-owned substantive authority rewrite was still uncommitted and temporarily incomplete. Work stopped without reverting that peer work. After the rewrite landed, formatting was reapplied to the new canonical revision and the review was repeated successfully. `git diff --check` was clean; Git emitted only its informational CRLF-to-LF normalization warning.
