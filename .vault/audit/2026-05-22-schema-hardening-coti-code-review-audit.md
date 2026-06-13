---
tags:
  - '#audit'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
  - '[[2026-05-22-schema-hardening-coti-adr]]'
  - '[[2026-05-22-schema-hardening-coti-research]]'
---



# `schema-hardening-coti` Code Review

REVIEW-2026-05-22-001 | INFO | Quoted-fund `coti` burn-down review passes

Reviewed the implementation against the focused research, accepted ADR, plan,
audit, and tests. No LOW, MEDIUM, HIGH, or CRITICAL issues were found.

The implementation removes only `coti` from broad optional-token stripping and
marks only the six source-reviewed warning-exposed Modelo 100 quoted-fund rows
as intentional singletons. It does not change other optional tokens, numeric
stripping, result rows, or the `2233` role previously flagged for possible
rename review.

Verification reviewed:

- Focused semantic-role tests passed.
- Touched validator/test ruff check passed.
- Cross-revision singleton drift, Modelo 100 registry tests, and committed
  registry tests passed.
- Direct Modelo 100/200 warning probe returned zero warnings.
- Coti plan structure, feature-scoped frontmatter, and feature-scoped dangling
  checks passed.
- `git diff --check` reported no whitespace errors, only CRLF warnings from
  the dirty worktree.
