---
tags:
  - "#exec"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-plan]]"
  - "[[2026-04-16-google-workspace-mcp-auth-research]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr-audit]]"
  - "[[2026-04-16-google-workspace-mcp-auth-plan-audit]]"
---

# `google-workspace-mcp-auth` `phase-1` `step-1`

Delivered the launcher-backed `google-workspace` MCP integration for Issue `#153`.

- Modified: `.mcp.json`
- Modified: `.gitignore`
- Created: `src/aeat/entrypoints/mcp/__init__.py`
- Created: `src/aeat/entrypoints/mcp/launch_google_workspace.py`
- Created: `src/aeat/entrypoints/mcp/test_launch_google_workspace.py`

## Description

Added a dedicated `aeat.entrypoints.mcp.launch_google_workspace` shim that loads project settings from `env/.env`, validates that either a complete OAuth desktop client or a service-account key path is configured, resolves service-account paths against `PROJECT_ROOT`, exports the exact upstream environment variables `workspace-mcp` expects, hard-pins the upstream credential cache into `env/workspace-mcp-credentials`, and then `exec`s the real `workspace-mcp` process.

The shipped launcher hardens two upstream integration edges discovered during execution:

- service-account mode now exports both `GOOGLE_IMPERSONATE_EMAIL` and upstream-required `USER_GOOGLE_EMAIL`, preventing the fresh-clone launcher path from failing schema defaults for Drive tools;
- process replacement now resolves the concrete `uvx` executable from the launch `PATH` before `os.execvpe`, which avoids Windows process replacement ambiguity while keeping the actual runtime handoff unchanged.

Rewired `.mcp.json` to invoke the launcher through `uv run python -m aeat.entrypoints.mcp.launch_google_workspace` with no tracked `env` block so secrets stay outside version control. Hardened `.gitignore` to keep the repo-local refresh-token cache out of git. Added pure `@pytest.mark.unit` coverage for OAuth passthrough, partial-OAuth rejection, missing-credential rejection, service-account path resolution, missing service-account files, and credential-directory creation.

The boundary test contract uses a hidden `--dump-launch-spec` probe that exercises the real settings loader and executable resolution path while redacting `GOOGLE_OAUTH_CLIENT_SECRET` from the serialized payload. This keeps the subprocess proof stable on Windows and preserves the no-secret test artifact invariant.

Runtime evidence gathered during execution:

- `uv run aeat bootstrap` under a temporary gitignored service-account env proved the repo can load local credentials headlessly, but consumer-account Drive ownership failed with Google `storageQuotaExceeded`, matching the documented quota limitation.
- `uv run aeat doctor` passed all required checks with the temporary local service-account env and confirmed the Drive surface was reachable for read-only verification.
- `uv run python -m aeat.entrypoints.mcp.launch_google_workspace --single-user --transport streamable-http` successfully exposed an MCP endpoint at `http://127.0.0.1:8000/mcp`, and an MCP client session completed `initialize` and `tools/list` against the launcher-backed server.
- A read-only Drive tool call still required an OAuth client path inside upstream `workspace-mcp`; that remaining live-proof gap has been escalated as follow-up Issue `#154` because the issue scope here is the secure launcher bridge, not autonomous OAuth desktop provisioning.

## Tests

- `uv run pytest src/aeat/entrypoints/mcp/test_launch_google_workspace.py tests/test_config.py`
- `uv run ruff check src/aeat/mcp tests/test_config.py`
- `uv run ty check src/aeat/mcp`
- `just lint`
- `just typecheck`
- `just test`
- `just hooks`
- `git check-ignore -v env/.env env/sa.json env/workspace-mcp-credentials`
- `git grep -n "GOCSPX-|a6eef783b-|finance-339817/locations/global/oauthClients/aeat-mcp-local" -- . ':!env/*' ':!*.log'` (no tracked secret hits)
