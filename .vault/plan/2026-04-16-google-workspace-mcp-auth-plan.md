---
tags:
  - "#plan"
  - "#google-workspace-mcp-auth"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-google-workspace-mcp-auth-research]]"
  - "[[2026-04-16-google-workspace-mcp-auth-reference]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr]]"
  - "[[2026-04-16-google-workspace-mcp-auth-adr-audit]]"
---

# `google-workspace-mcp-auth` `phase-1` plan

Implement the fresh-clone authentication fix for issue `#153` by inserting a project-owned launcher between `.mcp.json` and `workspace-mcp`, hardening the server's credential cache to a repo-local gitignored path, and verifying that the committed tree remains secret-free.

## Proposed Changes

The implementation follows the accepted ADR and its audit findings. The work stays narrow:

- add a small `aeat.entrypoints.mcp` package with a launcher module for the `google-workspace` MCP server
- bridge existing repo settings into the exact upstream `workspace-mcp` auth env vars, including the preserved service-account impersonation path
- redirect upstream credential persistence into a repo-local gitignored directory under `env/`
- rewire `.mcp.json` to execute the launcher through `uv run python -m ...` with no embedded secrets and no `env` block
- add deterministic `@pytest.mark.unit` coverage for the launcher behavior
- record execution, run local quality gates, and explicitly prove that no secrets leaked into committed files

## Tasks

- `Phase 1 — Launcher module`
  1. Create `src/aeat/entrypoints/mcp/` and add the launcher module plus package init files.
  2. Structure the launcher as pure derivation helpers plus a thin process-replacement boundary so env and argv behaviour can be unit tested without mocks or patched process APIs.
  3. Implement settings loading, auth-path validation, upstream env-var mapping, project-local credential-directory creation, and process replacement into the real `workspace-mcp` command.
  4. Ensure the launcher preserves the supported service-account path by mapping `GOOGLE_APPLICATION_CREDENTIALS` to `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` and passing through `GOOGLE_IMPERSONATE_EMAIL` when present.

- `Phase 2 — Tracked config handoff`
  1. Update `.mcp.json` so `google-workspace` runs the new launcher through `uv run python -m aeat.entrypoints.mcp.launch_google_workspace`.
  2. Update `.gitignore` only as needed to make the chosen `workspace-mcp` credential-cache path explicitly gitignored and auditable.

- `Phase 3 — Unit verification`
  1. Add launcher unit tests covering OAuth env passthrough, clear failure when neither auth path is configured, and the service-account fallback path.
  2. Keep the tests real-behavior and deterministic without mocks, patches, monkeypatches, or fake process runners.

- `Phase 4 — Execution records and local gates`
  1. Write the required execution step record for the implementation slice.
  2. Run `just lint`, `just typecheck`, `just test`, and `just hooks`, fixing any regressions within scope.
  3. Run a targeted secret-leak proof, including `git grep` coverage for Google OAuth key names and inspection that `.mcp.json` still has no `env` block or literal secrets.

- `Phase 5 — Runtime proof`
  1. Execute the repaired launch path against the real local credential store, including the `.mcp.json` handoff to the launcher and a real `google-workspace` MCP operation against a known Drive fixture or file ID.
  2. Record the concrete proof inputs and outputs in the execution log, including the restart boundary and the MCP operation used to show the server now authenticates on this worktree.
  3. Prove that runtime-generated credential artifacts stay only in ignored repo-local paths by checking the chosen `WORKSPACE_MCP_CREDENTIALS_DIR` and confirming Git ignores `env/.env`, `env/oauth-client.json` if present, and the credential-cache directory.

- `Phase 6 — Final review and publication`
  1. Run a mandatory vaultspec code review over the completed diff and vault artifacts.
  2. Commit the feature in focused conventional-commit form.
  3. Open a PR for issue `#153` with the vault artifacts and verification notes attached.
  4. If automated review feedback arrives during this execution cycle, action any in-scope findings and open follow-up issues for newly discovered out-of-scope risks.

## Parallelization

The code change itself is small and tightly coupled, so execution should stay mostly serial. The only intentional parallel work is delegated auditing: the ADR audit already ran in parallel with implementation-target inspection, and the final code review may again be delegated to a reviewer persona while local verification commands run.

## Verification

Mission success requires all of the following:

- a fresh local launch path exists where `.mcp.json` stays committed and secret-free, yet `workspace-mcp` receives the repo-local credentials it needs
- the launcher forces the upstream credential cache into a gitignored repo-local directory instead of the default user-global home path
- the launcher is shaped so the env/argv derivation can be unit tested without patched process runners
- unit tests prove the three required launcher behaviors from issue `#153`
- `tests/test_config.py` still passes without unrelated config drift
- `just lint`, `just typecheck`, `just test`, and `just hooks` are green
- a real MCP launch on this worktree proves the repaired `.mcp.json` path authenticates successfully and can perform at least one Drive operation
- post-launch checks prove the runtime credential artifacts stayed in ignored repo-local paths and did not fall back to the upstream home-directory cache
- a post-implementation `git grep` confirms there are no copied OAuth values or secret-bearing tracked config changes
- the PR description captures the launcher design, the token-cache hardening choice, the verification results, and any follow-up work opened during the cycle
