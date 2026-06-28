---
tags:
  - "#adr"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-research]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
  - "[[2026-04-12-gsuite-bootstrap-adr]]"
---

# `google-workspace-mcp-auth` adr: `issue-153-launcher-shim-and-project-local-credential-cache` | (**status:** `accepted`)

## Problem Statement

The committed `google-workspace` MCP entry fails on a fresh clone because `workspace-mcp` starts before the repo's gitignored `env/.env` values are loaded into the process environment. The server therefore misses the locally provisioned OAuth credentials, falls back to a package-local `client_secret.json`, and aborts. The same launch path also leaves refresh-token persistence on upstream defaults, which means credential state lands outside the worktree unless explicitly redirected.

## Considerations

- The repo already has one canonical secret source: `src/aeat/config.py` loading `env/.env`.
- The issue's security invariant is strict: `.mcp.json` stays committed and secret-free.
- Verified upstream `workspace-mcp` inputs match the repo's existing OAuth desktop env vars, but service-account mode expects `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` rather than the repo's `GOOGLE_APPLICATION_CREDENTIALS`.
- Verified upstream token persistence is controlled by `WORKSPACE_MCP_CREDENTIALS_DIR`, with a user-global home-directory default if unset.
- The narrowest safe fix is a project-owned launcher that bridges env values into the child process just before exec, rather than broadening the tracked config surface or teaching `.mcp.json` about secrets.

## Constraints

- The launcher must run from the project environment via `uv run python -m ...`, because `.mcp.json` may not embed secrets or ad hoc env blocks.
- The design must preserve both supported repo auth paths:
  - OAuth desktop credentials from `env/.env`
  - Service-account credentials via `GOOGLE_APPLICATION_CREDENTIALS`
- The fix must remain worktree-local and deterministic on Windows and Linux.
- Unit tests must avoid mocks, patches, stubs, and monkeypatch shortcuts.

## Implementation

- Add a new `aeat.entrypoints.mcp` package with `launch_google_workspace.py` as the dedicated bridge for the `google-workspace` MCP server.
- The launcher will:
  - load `Settings` via `aeat.core.config.load_settings()`
  - validate that either OAuth desktop credentials or a service-account key path is configured
  - copy the repo-owned settings into the exact upstream env vars `workspace-mcp` expects
  - map `GOOGLE_APPLICATION_CREDENTIALS` to `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`
  - pass through `GOOGLE_IMPERSONATE_EMAIL` unchanged when it is configured so the preserved service-account impersonation path does not regress
  - force `WORKSPACE_MCP_CREDENTIALS_DIR` to a project-local gitignored directory under `env/`
  - create that credential directory before exec so the upstream credential store never falls back to a home-directory cache
  - replace the current process with the real server invocation
- `.mcp.json` will be rewired from direct `uvx workspace-mcp` execution to `uv run python -m aeat.entrypoints.mcp.launch_google_workspace`, with no `env` block.
- The credential cache path is fixed in code as a repo-local path under `env/` rather than introduced as a new `Settings` field, because this issue is about securely consuming the existing credential store, not adding a new operator-facing secret surface.
- The execution and verification phases must explicitly prove that the new credential-cache location remains a secret surface only in gitignored paths and that the committed tree still contains no copied OAuth values, secret-bearing `env` blocks, or `.mcp.json` secret leakage.

## Rationale

The launcher shim is the only design that satisfies all of the issue constraints simultaneously. It lets the repo keep secrets in the already-established gitignored `env/` container, keeps `.mcp.json` auditable and secret-free, and does not depend on the editor or MCP host to understand project-specific env-file loading. Using the existing `Settings` model avoids duplicate parsing logic and ensures the same canonical credential paths drive both the repo code and the MCP launch path.

Pinning `WORKSPACE_MCP_CREDENTIALS_DIR` to a repo-local directory is the hardening move that closes the second secret surface. Upstream defaults are user-global and therefore cross-worktree; that is convenient for a standalone tool but wrong for this repo's isolation model. Keeping the path fixed and internal to the launcher is preferable to adding a new setting because the operator should not need to reason about yet another credential location for this bug fix.

## Consequences

- `workspace-mcp` refresh tokens and per-user credential files will move under a gitignored repo-local directory instead of `~/.google_workspace_mcp/credentials`.
- Service-account launches will now work through the MCP shim without requiring operators to learn upstream's alternate env var name.
- Service-account impersonation remains in scope because `GOOGLE_IMPERSONATE_EMAIL` will cross the launcher boundary unchanged when configured.
- The project gains a small `aeat.entrypoints.mcp` package and a focused launcher unit-test surface.
- Fresh-clone startup becomes deterministic, but any future change to upstream auth env names will require updating the launcher bridge explicitly rather than silently inheriting new defaults.
