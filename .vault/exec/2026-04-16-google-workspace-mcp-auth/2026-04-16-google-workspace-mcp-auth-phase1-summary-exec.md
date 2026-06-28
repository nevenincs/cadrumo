---
tags:
  - "#exec"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-plan]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr]]"
  - "[[2026-04-16-google-workspace-mcp-auth-research]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr-audit]]"
  - "[[2026-04-16-google-workspace-mcp-auth-plan-audit]]"
---

# `google-workspace-mcp-auth` `phase-1` summary

Delivered the Issue `#153` launcher fix that keeps `.mcp.json` secret-free while making the `google-workspace` MCP server inherit local credentials from `env/.env`.

- Modified: `.mcp.json`
- Modified: `.gitignore`
- Created: `src/aeat/entrypoints/mcp/__init__.py`
- Created: `src/aeat/entrypoints/mcp/launch_google_workspace.py`
- Created: `src/aeat/entrypoints/mcp/test_launch_google_workspace.py`
- Created: `.vault/research/2026-04-16-google-workspace-mcp-auth-research.md`
- Created: `.vault/reference/2026-04-16-google-workspace-mcp-auth-reference.md`
- Created: `.vault/adr/2026-04-16-google-workspace-mcp-auth-adr.md`
- Created: `.vault/plan/2026-04-16-google-workspace-mcp-auth-plan.md`
- Created: `.vault/audit/2026-04-16-google-workspace-mcp-auth-adr-audit.md`
- Created: `.vault/audit/2026-04-16-google-workspace-mcp-auth-plan-audit.md`
- Created: `.vault/exec/2026-04-16-google-workspace-mcp-auth/2026-04-16-google-workspace-mcp-auth-phase1-step1.md`
- Created: `.vault/exec/2026-04-16-google-workspace-mcp-auth/2026-04-16-google-workspace-mcp-auth-phase1-summary.md`

## Description

The feature now launches `workspace-mcp` through a project-owned shim instead of a direct `.mcp.json` command. The shim is responsible for loading AEAT settings, validating supported auth paths, resolving repo-relative credential files deterministically, mapping AEAT config fields to upstream `workspace-mcp` environment variables, and forcing the upstream token cache into a gitignored repo-local directory. The tracked MCP configuration no longer contains any secrets or secret-shaped environment blocks.

The final implementation also locks down two upstream-specific runtime details uncovered during execution:

- service-account launches now export `USER_GOOGLE_EMAIL` alongside `GOOGLE_IMPERSONATE_EMAIL`, matching the actual `workspace-mcp` tool schema contract;
- Windows process replacement resolves the concrete `uvx` executable before `os.execvpe`, and the boundary probe records that resolved path without leaking secret values.

Execution proved three separate properties:

- the pure launcher contract behaves correctly under unit tests for every supported auth branch;
- the repository-wide lint, typecheck, hooks, and test gates are green after the change;
- the launcher-backed MCP server can answer `initialize` and `tools/list` over HTTP when local credentials are present, while secret material remains confined to ignored local files.

One live-proof edge remains outside the change scope: a full read-only Drive tool call through upstream `workspace-mcp` still requires an OAuth desktop client flow, and the fallback headless service-account route on this consumer-account project cannot create Drive-owned scratch resources because Google returns `storageQuotaExceeded`. That operational gap is tracked separately in Issue `#154` rather than folded into the launcher fix.

## Tests

- `uv run pytest src/aeat/entrypoints/mcp/test_launch_google_workspace.py tests/test_config.py`
- `uv run ruff check src/aeat/mcp tests/test_config.py`
- `uv run ty check src/aeat/mcp`
- `just lint`
- `just typecheck`
- `just test`
- `just hooks`
- launcher-backed MCP `initialize` + `tools/list` over `http://127.0.0.1:8000/mcp`
- tracked-file secret scan via `git grep`
- git-ignore proof for `env/.env`, `env/sa.json`, and `env/workspace-mcp-credentials`
