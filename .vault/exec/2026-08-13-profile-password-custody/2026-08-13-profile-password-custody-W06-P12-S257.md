---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:caae0e05c5892dad048d1d431537a031a3ccca1ca1dd63dbddf4f1209681ff70'
step_id: 'S257'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Route CLI and manager censal apply through the canonical user-profile.censo-review operation, preserving one acquisition, encrypted reviewed operand, exact baseline, resume-without-reread, and apply_cotejo sole-writer authority

## Scope

- `src/cadrumo/application/user_profile/_censal_operation.py and src/cadrumo/entrypoints/cli/_config/ and src/cadrumo/adapters/inbound/tui/`

## Description

- Trace the accepted censo-review operation, frontend callers, encrypted operand, baseline, resume path, and writer authority with semantic discovery and exact caller inventory.
- Route CLI apply and manager/TUI apply through one shared submit, start, project, respond, and settle driver.
- Present the exact typed review projection once and preserve the durable reviewed operand across continuation and restart.
- Validate successful terminal condition, declared effect, and typed censal outcome before a frontend reports success.
- Remove the direct censal writer bypass and enforce the surviving `apply_cotejo` caller set with an AST gate.
- Exercise real CLI/TUI presentation, encrypted application apply and rejection, post-response failure honesty, stale-baseline refusal, and restart without reread.

## Outcome

CLI `censo pull --apply` and the manager action now enter the canonical `user-profile.censo-review` operation. The operation performs one acquisition, persists its reviewed operand through encrypted operation custody, binds the exact profile baseline, and applies only through `apply_cotejo`. Rejection leaves the record unchanged, stale or failed continuation is never rendered as success, and restart resumes from the durable operand without another live read.

Scoped verification passed: 29 CLI, TUI, facade, and executor tests; five restart, operand, and stale-baseline tests; three real frontend apply, reject, and terminal-failure tests; two real TUI review tests; Ruff; and scoped ty. The structural gate parses production ASTs, rejects any `apply_censal_read` declaration, and pins the exact `apply_cotejo` caller inventory.

## Notes

The first formal review rejected the temporary foreclosure because it did not implement ADR D9 and because its redeclaration proof was lexical. The second review confirmed full canonical routing but found terminal-state ambiguity and S257-owned hygiene debt; both S257 findings were corrected before final review.

The final independent review approved S257 with no remaining critical, high, or medium findings.

Concurrent shared-worktree activity created commit `916fc9517e`, which captured the main censo routing while this Step was executing, and later advanced HEAD with peer changes. Remaining whole-tree import-hygiene failures belong to an in-progress peer TUI relocation and unrelated test-debt changes; this Step did not rewrite, revert, or absorb those files.
