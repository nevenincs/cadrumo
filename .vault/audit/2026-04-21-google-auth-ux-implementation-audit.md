---
tags:
  - '#audit'
  - '#google-auth-ux'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-google-auth-ux-research]]'
  - '[[2026-04-21-google-auth-ux-adr]]'
  - '[[2026-04-21-google-auth-ux-phase-1-plan]]'
---

# `google-auth-ux` implementation audit

## Scope

Audit the implementation of the accepted Google auth UX contract across the CLI auth entrypoint, auth-path resolver, MCP launch contract, doctor, wrappers, and user-facing documentation.

## Findings

### Resolved in implementation

- The repo now has one deterministic auth-path resolver, so Desktop OAuth and service-account configuration no longer race implicitly.
- The new `aeat auth init` command gives Kent one guided entrypoint with path selection, local artifact preparation, and explicit next-step messaging.
- The doctor now reports the active path, CLI auth material, MCP cache readiness, inactive-path drift, and ADC state separately.
- Legacy wrapper copy was brought into line with the guided path instead of presenting independent auth narratives.
- Two independent code-review loops were run. The first surfaced real contract defects around service-account wrapper activation, premature path mutation, false MCP readiness, stale-token classification, and inactive-path truthfulness. Those findings were addressed and the follow-up reviewer verdict was: no findings remain.

### Residual operational issue

- Live workstation verification still found one real local blocker: the Desktop OAuth CLI token and MCP credentials are not currently in a usable state in this worktree. After the stricter readiness checks landed, `aeat auth init --path desktop-oauth-local-dev --no-acquire-cli-token --no-doctor` now fails immediately with the repair instructions instead of pretending readiness.
- `aeat doctor` now fails honestly on this workstation with required `Google auth readiness`, `CLI OAuth cache`, and `MCP credentials cache` rows until a fresh browser consent flow and first MCP launch occur.

## Verification

- `uv run pytest src/aeat/_test_auth.py src/aeat/entrypoints/cli/_test_auth.py src/aeat/entrypoints/cli/_test_doctor.py src/aeat/entrypoints/cli/_test_oauth.py src/aeat/entrypoints/mcp/test_launch_google_workspace.py tests/test_config.py -q`
- `uv run ruff check src/aeat/_test_auth.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py src/aeat/entrypoints/cli/auth.py src/aeat/entrypoints/cli/doctor.py src/aeat/entrypoints/cli/_test_auth.py src/aeat/entrypoints/cli/_test_doctor.py src/aeat/entrypoints/cli/_test_oauth.py src/aeat/entrypoints/mcp/launch_google_workspace.py src/aeat/entrypoints/mcp/test_launch_google_workspace.py src/aeat/config.py tests/test_config.py`
- `uv run ty check src/aeat/auth src/aeat/cli src/aeat/mcp src/aeat/config.py`
- `uv run prek run --files README.md CONTRIBUTING.md env/.env.example`
- `uv run aeat auth --help`
- `uv run aeat auth init --path desktop-oauth-local-dev --no-acquire-cli-token --no-doctor`
- `uv run python -m aeat.entrypoints.mcp.launch_google_workspace --dump-launch-spec`
- `uv run aeat doctor`

## Conclusion

The implementation contract is in place, verified, and closed through review. The remaining issue is operational state on this workstation, not missing UX scaffolding: Kent now gets a direct diagnosis and the exact re-consent or first-launch actions needed to clear the missing Desktop OAuth token and missing MCP credentials.
