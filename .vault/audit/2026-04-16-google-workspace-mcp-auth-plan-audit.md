---
tags:
  - '#audit'
  - '#google-workspace-mcp-auth'
date: '2026-04-16'
modified: '2026-04-16'
related:
  - '[[2026-04-16-google-workspace-mcp-auth-research]]'
  - '[[2026-04-16-google-workspace-mcp-auth-reference]]'
  - '[[2026-04-16-google-workspace-mcp-auth-adr]]'
  - '[[2026-04-16-google-workspace-mcp-auth-adr-audit]]'
  - '[[2026-04-16-google-workspace-mcp-auth-plan]]'
---

# `google-workspace-mcp-auth` Code Review

### VERIFY-001 | HIGH | Plan never schedules the issue's required fresh-clone MCP boot proof

The issue acceptance is an end-to-end integration contract: fresh clone or fresh
worktree bootstrap, operator credential provisioning, host restart, successful
`google-workspace` MCP boot, and a real Drive operation through the MCP server.
The plan's `Phase 4` and `Verification` sections stop at unit coverage, local
quality gates, and static secret checks, then restate the desired outcome as "a
fresh local launch path exists." That is weaker than proving the broken boundary
is fixed. An implementation could satisfy the current plan while never showing
that the tracked `.mcp.json` entry now launches a working server inside a new
worktree. Add an explicit execution task and recorded evidence for the full
bootstrap plus restart plus real MCP call sequence, including the concrete Drive
fixture or file ID used for the proof.

### SECURITY-002 | MEDIUM | Secret-surface verification is static only and does not prove runtime credential artifacts stay in ignored repo-local paths

The issue and ADR both treat the refresh-token cache as a second secret surface,
not merely a path-setting detail. The plan proves only that tracked files remain
secret-free through `git grep` and `.mcp.json` inspection. It does not require a
post-launch check that `env/.env`, `env/oauth-client.json`, and the chosen
`WORKSPACE_MCP_CREDENTIALS_DIR` are all ignored by Git, nor does it require
evidence that first-run consent did not write credential files into the upstream
home-directory default. Add explicit runtime proof such as `git check-ignore`
or `git status --ignored` coverage plus a cache-location check after a real
launch.

### TEST-003 | MEDIUM | Phase 3 is not concrete enough to satisfy the no-mocks rule around process replacement

The launcher must load settings, derive child-process env vars, create a
credential directory, and replace the current process. `Phase 3` correctly bans
mocks, patches, monkeypatches, and fake process runners, but it never states how
the launcher will be structured so those behaviours remain testable under that
rule. Without an explicit seam such as a pure helper that derives env plus argv
from real fixture inputs, plus a thin `exec` boundary, implementers are likely
to fall back to forbidden patching or to leave the `exec` contract effectively
untested. The plan should add that code-shape requirement up front rather than
leaving it implicit.

### SCOPE-004 | LOW | Final phase adds an open-ended publication loop that exceeds a bounded implementation plan

`Phase 5` goes beyond delivering issue `#153` into "open a PR," "wait for
automated review feedback," "action any review findings," and "open follow-up
issues." Those are legitimate delivery tasks, but they are not bounded execution
work for this issue and they depend on external review cycles. Keeping them in
the implementation plan makes "done" ambiguous and introduces avoidable scope
creep. The plan should stop at implementation, verification, vault artifacts,
and a concise handoff; PR review response belongs in a separate execution loop
or follow-up plan.
