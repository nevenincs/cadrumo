---
tags:
  - "#audit"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-research]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr]]"
---

# `google-workspace-mcp-auth` Code Review

Audit of `issue #153` against the linked research, reference, and ADR artifacts,
with specific attention to the secret-free `.mcp.json` invariant.

### AUTH-001 | MEDIUM | ADR drops the `GOOGLE_IMPERSONATE_EMAIL` launcher obligation

`Issue #153` and the reference both treat the supported service-account path as
the mapped `GOOGLE_APPLICATION_CREDENTIALS` key file plus passthrough
`GOOGLE_IMPERSONATE_EMAIL`. The ADR implementation only commits to mapping
`GOOGLE_APPLICATION_CREDENTIALS` to `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` and to
copying repo-owned settings into the upstream auth env vars that
`workspace-mcp` validates directly. Because `GOOGLE_IMPERSONATE_EMAIL` is a
repo-owned bridge input rather than one of those validated upstream config vars,
an implementation can satisfy the ADR while silently omitting impersonation and
therefore breaking the service-account path the issue explicitly keeps in scope.
The ADR should make this passthrough a required launcher responsibility.

### POLICY-002 | LOW | ADR does not preserve the explicit hardening proof for the new credential cache

The ADR correctly keeps `.mcp.json` secret-free and redirects
`WORKSPACE_MCP_CREDENTIALS_DIR` to a repo-local path, but it stops at the path
decision. `Issue #153` also requires the runtime-generated credential cache to
be treated as an explicit secret surface: document the gitignore coverage for
the chosen directory and verify that committed files still contain no copied
OAuth values or secret-bearing `env` blocks. Because the ADR omits that
obligation, the implementation plan can read as "set a local path" rather than
"set a local path and prove the committed tree stayed secret-free," which weakens
the audit trail around the second credential surface.
