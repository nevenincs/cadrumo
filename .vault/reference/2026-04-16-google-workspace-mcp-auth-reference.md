---
tags:
  - "#reference"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-research]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
---

# `google-workspace-mcp-auth` reference: `launcher-inputs-and-upstream-env-contract`

This reference captures the exact repo and upstream code surfaces the launcher shim must mediate for issue `#153`.

## Repo-owned source of truth

- `src/aeat/config.py`
  - `PROJECT_ROOT` resolves from the repo root and already anchors the canonical `env/.env` path.
  - `load_settings()` returns a `Settings` instance populated from `env/.env`.
  - Existing fields provide all required launcher inputs without adding new secrets to the repo config surface.
- `.mcp.json`
  - Current `google-workspace` entry invokes `uvx workspace-mcp --tool-tier core` directly.
  - This is the only committed launch path that needs to change for the issue.
- `.gitignore`
  - Already ignores `env/*` except `env/.env.example`.
  - Already ignores `.tokens/`.
  - Needs an explicit ignore for the chosen `workspace-mcp` credential-cache directory if that directory is new.

## Upstream `workspace-mcp` auth contract

- `auth/oauth_config.py`
  - Reads `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`.
  - Reads service-account inputs `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` and `GOOGLE_SERVICE_ACCOUNT_KEY_JSON`.
  - Declares service-account mode enabled when one of those service-account env vars is present.
- `auth/google_auth.py`
  - `load_client_secrets_from_env()` builds OAuth client config directly from `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and optional `GOOGLE_OAUTH_REDIRECT_URI`.
  - `create_oauth_flow()` prefers those env vars and only falls back to `client_secret.json` under the installed package tree if the env vars are absent.
  - `check_client_secrets()` emits the failure mode observed in the issue when both env vars and file fallback are absent.

## Upstream persisted credential state

- `auth/credential_store.py`
  - Uses `WORKSPACE_MCP_CREDENTIALS_DIR` as the preferred credential-directory override.
  - Falls back to `GOOGLE_MCP_CREDENTIALS_DIR` for backward compatibility.
  - Otherwise defaults to `~/.google_workspace_mcp/credentials`.
  - Stores one JSON file per authenticated user email.
- `auth/google_auth.py`
  - Uses the same credential-directory env vars when searching for cached credentials.
  - Persists refreshed credentials back into the credential store when running in stateful mode.

## Required launcher responsibilities

- Load `Settings` from the repo-local `env/.env` file before any child process is spawned.
- Validate that one supported upstream auth path is configured:
  - OAuth desktop path: `GOOGLE_OAUTH_CLIENT_ID` plus `GOOGLE_OAUTH_CLIENT_SECRET`
  - Service-account path: `GOOGLE_APPLICATION_CREDENTIALS` in repo settings, exported to upstream as `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
- Export `GOOGLE_OAUTH_REDIRECT_URI` when present so the MCP server sees the same redirect URI the repo already documents.
- Export `GOOGLE_IMPERSONATE_EMAIL` unchanged because upstream service-account mode may consume it indirectly through tool logic even though the config module does not validate it itself.
- Export `WORKSPACE_MCP_CREDENTIALS_DIR` to a gitignored project-local directory so refresh tokens and session files are isolated per worktree.
- Replace the current process with `uvx workspace-mcp --tool-tier core` (or an equivalent `uv`-managed exec) rather than starting a nested long-lived child and proxying stdio manually.

## Reference conclusions

- No new secret-bearing setting is required in `src/aeat/config.py` for the auth bridge itself.
- The only additive config surface likely needed is a project-local path for the `workspace-mcp` credential directory if the launcher should not hardcode it relative to `PROJECT_ROOT`.
- The implementation should stay small and explicit: validate inputs, set upstream env vars, ensure the credential directory exists, then `exec`.
