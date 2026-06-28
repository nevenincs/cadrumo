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
  - '[[2026-04-16-google-workspace-mcp-auth-plan-audit]]'
---

# `google-workspace-mcp-auth` Code Review

Status: `PASS`

The final implementation satisfies the issue scope and keeps `.mcp.json` secret-free. The launcher now preserves the repo's existing auth precedence rules, passes through supported upstream service-account variables without over-constraining them locally, resolves the concrete `uvx` executable before process replacement, and keeps the upstream credential cache in a repo-local gitignored directory.

`src/aeat/entrypoints/mcp/test_launch_google_workspace.py` covers the launcher handoff, OAuth env passthrough, service-account env passthrough, stale service-account fallback to OAuth, repo-local credential-cache creation, and the subprocess-backed `--dump-launch-spec` boundary. The dump probe redacts `GOOGLE_OAUTH_CLIENT_SECRET` in its serialized output.

Residual risk: there is still no live fresh-worktree Drive operation in the automated suite. The diagnostic `--dump-launch-spec` flag remains test-only and should stay out of operator workflows and log-capturing CI paths.

## 2026-04-16 current review findings

AUTH-001 | MEDIUM | Stale service-account config blocks valid OAuth launches

`_require_supported_credentials()` raises as soon as `GOOGLE_APPLICATION_CREDENTIALS` points at a missing file, even when `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are both complete. That is stricter than the repo's existing auth resolver in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`, which falls back to OAuth when the service-account file is absent, and it can break otherwise valid launcher runs on worktrees with leftover service-account config.

AUTH-002 | MEDIUM | Service-account launches are over-constrained on impersonation

The launcher rejects any service-account launch unless `GOOGLE_IMPERSONATE_EMAIL` is present. The issue and the reference treat impersonation as a passthrough when configured, not as a hard prerequisite, so this blocks service-account setups that only need `GOOGLE_APPLICATION_CREDENTIALS` mapped to `GOOGLE_SERVICE_ACCOUNT_KEY_FILE`.

## 2026-04-16 re-review after follow-up fixes

Status: `PASS`

The follow-up changes close the prior findings: stale `GOOGLE_APPLICATION_CREDENTIALS` no longer blocks OAuth when a complete OAuth desktop configuration is present, and service-account launches now pass through when the service-account env vars exist without requiring impersonation.

Residual risk: the launcher still exposes a `--dump-launch-spec` diagnostic path for boundary testing, so any future logging or CI wiring should keep that flag out of operator workflows and out of secret-bearing log captures.
