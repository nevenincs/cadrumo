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
  - '[[2026-04-21-google-auth-ux-contract-review-audit]]'
---

# `google-auth-ux` Code Review

GAUTH-001 | CRITICAL | `just gsuite-bootstrap-sa` does not actually activate the service-account path
`justfile:398-423` and `justfile:425-453` create `env/sa.json` and then immediately run `aeat bootstrap` / `aeat doctor`, but they never write `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_AUTH_PATH` into `env/.env`. The surrounding copy in `justfile:398-403` and `README.md:240-244` says the wrapper sets that state, so the current implementation can leave the resolver on the previous path or on no path at all while presenting the wrapper as complete. There is no adjacent test coverage for the `just` wrapper contract.

GAUTH-002 | HIGH | `aeat auth init` can break a working configuration before the new path is valid
`src/aeat/entrypoints/cli/auth.py:148-149` writes `GOOGLE_AUTH_PATH` to the requested path before any Desktop OAuth JSON or service-account key validation succeeds. The failure branches at `src/aeat/entrypoints/cli/auth.py:152-155`, `src/aeat/entrypoints/cli/auth.py:185-213`, and `src/aeat/entrypoints/cli/auth.py:273-306` then exit after printing guidance, leaving `env/.env` on a blocking path selection. A user exploring the other path can therefore strand an otherwise working config just by asking for instructions. `src/aeat/entrypoints/cli/_test_auth.py:17-75` only covers happy-path imports and misses this regression.

GAUTH-003 | HIGH | Doctor treats an empty MCP credentials directory as MCP-ready
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py:88-90` distinguishes a populated MCP cache from a merely existing directory, but `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py:117-122` still marks `mcp_ready` true when the directory exists and is empty. `src/aeat/entrypoints/cli/doctor.py:323-345` then reports the MCP cache row as `OK` for that empty directory, and `src/aeat/entrypoints/cli/doctor.py:224-244` can promote overall Google-auth readiness to `OK` once the CLI side is also ready. That makes `aeat auth init --prepare-mcp` look like a completed MCP auth flow even though no `workspace-mcp` credential file has been written yet. The current tests only lock in the directory-exists behaviour (`src/aeat/entrypoints/cli/_test_doctor.py:207-225`) and do not guard against the false full-success state.

GAUTH-004 | HIGH | Stale or corrupt Desktop OAuth tokens are classified as ready until a later API call fails
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py:81-82` and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py:109-114` reduce CLI readiness to token-file existence. `src/aeat/entrypoints/cli/auth.py:215-233` only reacquires a token when the cache file is missing, so a stale or malformed token file skips the guided consent step entirely. `src/aeat/entrypoints/cli/doctor.py:297-309` likewise reports the CLI OAuth cache row as `OK` on file presence alone. Actual validation only happens much later in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py:251-259` when a command tries to load or refresh the token, which means the operator sees a ready-looking state first and the actionable failure second. There is no adjacent test for revoked, malformed, or scope-stale token files.

GAUTH-005 | MEDIUM | Inactive-path drift reporting is too narrow to be a truthful ignored-state diagnostic
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_google_paths.py:97-106` only reports drift for a missing inactive service-account file or a partial inactive Desktop OAuth config. A fully configured inactive path is silent, and an invalid inactive service-account JSON falls through to the generic `service-account key state` warning path in `src/aeat/entrypoints/cli/doctor.py:736-768` instead of being labeled ignored drift. The desktop row in `src/aeat/entrypoints/cli/doctor.py:253-282` similarly reports plain `OK` / `WARN` states without telling the operator when that material belongs to the inactive path. That leaves `aeat doctor` unable to consistently satisfy the ADR requirement to separate active-path failures from ignored stale optional config. Coverage only exercises one missing-service-account drift case (`src/aeat/entrypoints/cli/_test_doctor.py:239-250`).
