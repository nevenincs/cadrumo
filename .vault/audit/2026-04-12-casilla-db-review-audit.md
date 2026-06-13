---
tags:
  - '#audit'
  - '#casilla-db'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-casilla-db-research]]'
  - '[[2026-04-12-casilla-db-adr]]'
  - '[[2026-04-12-casilla-db-plan]]'
---

# `casilla-db` Code Review

Validation during review: `just lint`, `just typecheck`, `just test`, and `just hooks` all passed on the current tree.

POLICY-001 | MEDIUM | Reviewer enforcement still does not enforce a real human-review boundary
`src/aeat/domain/casillas/catalogue.py:77-95` only checks that `reviewed_by.strip()` is non-empty and that `reviewed_at` is present, while `src/aeat/domain/casillas/models.py:96-97` still models those fields as free-form string plus nullable date. The checked-in corpora continue to use `reviewed_by: "codex"` throughout `corpus/casillas/`, and `docs/casillas.md:221` explicitly documents the policy as “non-empty `reviewed_by` plus non-null `reviewed_at`”. This satisfies the literal metadata requirement and `aeat casillas verify` correctly rejects missing fields, but it still does not distinguish actual human review from automated self-approval.

LLM-002 | MEDIUM | The issue-21-dependent commands remain unimplemented relative to issue #23
The new behavior is cleaner than the earlier stub-draft path: `src/aeat/entrypoints/cli/casillas.py:58-87` now fails clearly with an issue-21 dependency message, and the live test at `src/aeat/domain/casillas/test_live_cli.py:19-22` explicitly skips until the real client lands. That said, this is still a functional deviation from issue `#23`, which asked for LLM-assisted extraction and translation commands plus one opt-in live round-trip per modelo through the real provider. The branch now advertises the dependency boundary correctly, but the requested provider-backed workflows are still deferred.
