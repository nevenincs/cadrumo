---
tags:
  - "#research"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-12-gsuite-bootstrap-research]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
---

# `google-workspace-mcp-auth` research: `issue-153-fresh-clone-authentication`

This research grounds issue `#153`, a fresh-clone bug in the committed `google-workspace` MCP entry. The narrow scope is the bridge between the repo's gitignored credential store and the `workspace-mcp` child-process environment, plus the placement of that server's refresh-token cache.

## Findings

### Current repo credential contract

- `src/aeat/config.py` is the canonical loader for local operator credentials.
- `Settings.model_config.env_file` points at `PROJECT_ROOT / "env" / ".env"`.
- The existing Google credential fields already cover the launcher inputs this issue needs:
  - `google_oauth_client_id` -> `GOOGLE_OAUTH_CLIENT_ID`
  - `google_oauth_client_secret` -> `GOOGLE_OAUTH_CLIENT_SECRET`
  - `google_oauth_redirect_uri` -> `GOOGLE_OAUTH_REDIRECT_URI`
  - `google_application_credentials` -> `GOOGLE_APPLICATION_CREDENTIALS`
  - `google_impersonate_email` -> `GOOGLE_IMPERSONATE_EMAIL`
  - `aeat_token_dir` -> `AEAT_TOKEN_DIR`
- The tracked `.mcp.json` entry for `google-workspace` currently executes `uvx workspace-mcp --tool-tier core` directly, with no project-owned launcher layer and no `env` block.

### Current security boundary

- `env/*` is gitignored, with `!env/.env.example` explicitly carved out.
- `.gitignore` also ignores `.tokens/`, which is the repo's existing OAuth cache directory for AEAT-side browser and Google helper flows.
- The issue's non-negotiable invariant is therefore already aligned with the repo's scaffolding design: secrets belong under `env/` or other gitignored local paths, not in committed launcher config.

### Verified upstream `workspace-mcp` OAuth inputs

- The installed `workspace-mcp` distribution available via `uvx --from workspace-mcp` is version `1.19.0`.
- Its OAuth configuration lives in flat top-level modules under the wheel cache, not under a `workspace_mcp` package namespace.
- `auth/oauth_config.py` reads:
  - `GOOGLE_OAUTH_CLIENT_ID`
  - `GOOGLE_OAUTH_CLIENT_SECRET`
  - `GOOGLE_OAUTH_REDIRECT_URI`
  - `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  - `GOOGLE_SERVICE_ACCOUNT_KEY_JSON`
- `auth/google_auth.py` separately reads legacy client-secret path vars:
  - `GOOGLE_CLIENT_SECRET_PATH`
  - `GOOGLE_CLIENT_SECRETS`
- `auth/google_auth.py` prefers inline OAuth env vars first and only falls back to a package-local `client_secret.json` file when those vars are absent.

### Verified upstream credential-cache behavior

- `workspace-mcp` persists OAuth credentials through `auth/credential_store.py`.
- The preferred env var for the credential directory is `WORKSPACE_MCP_CREDENTIALS_DIR`.
- `GOOGLE_MCP_CREDENTIALS_DIR` remains as a backward-compatible fallback.
- When neither env var is set, the default credential directory is user-global:
  - `~/.google_workspace_mcp/credentials`
  - falling back to `./.credentials` only if the home directory cannot be resolved
- Credential files are stored one JSON file per user email with mode `0600` on creation.
- The in-memory OAuth 2.1 session store does not change the persisted file location; refreshed tokens are still written back through the local credential store when stateful mode is active.

### Mapping gap between repo settings and upstream expectations

- The repo stores service-account credentials as `GOOGLE_APPLICATION_CREDENTIALS`, but `workspace-mcp` expects `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`.
- The repo stores OAuth desktop credentials directly in `env/.env`, which matches upstream expectations for `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI`.
- No existing repo code maps `GOOGLE_APPLICATION_CREDENTIALS` to `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` for child processes.
- No existing repo code points `workspace-mcp` at a project-local credential directory, so a fresh consent flow would write refresh tokens into the user's home directory rather than a worktree-isolated gitignored location.

### Failure mode on a fresh clone

- On a fresh clone, the parent Codex/Claude process does not automatically export `env/.env` into its own environment before `.mcp.json` launches the server.
- Because `.mcp.json` starts `workspace-mcp` directly, the child only sees the bare parent environment.
- `workspace-mcp` then fails its env lookup, falls back to its package-local `client_secret.json`, and errors because that file is not present in the uvx cache layout.

## Outcome

- The repo already has the right canonical secret source: `env/.env` through `aeat.core.config.Settings`.
- The missing piece is a project-owned launcher that loads `Settings`, validates one of the supported auth paths, maps the repo's service-account variable to upstream's expected variable, and then `exec`s the real `workspace-mcp` process.
- The same launcher should hard-pin `WORKSPACE_MCP_CREDENTIALS_DIR` to a gitignored project-local directory so refresh tokens never default to a shared home-directory cache.
