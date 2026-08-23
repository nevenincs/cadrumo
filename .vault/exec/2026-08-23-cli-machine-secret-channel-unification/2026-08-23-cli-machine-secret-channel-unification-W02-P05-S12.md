---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7ea8b32c1aaddd565e3b2a12afe27f2a9dbb9fb341545106b08ff65fb9f8bdce'
step_id: 'S12'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and remove obsolete imports, models, manual injection, CLI environment routes, direct readers, and prompts outside the closed inventory while retaining separately governed core and programmatic settings

## Scope

- `src/cadrumo/entrypoints/cli/ and its tests`

## Description

- Ground the scalar-secret implementation and governing decisions through semantic discovery, then confirm the complete production and test census with exact symbol searches.
- Remove the login gate's implicit environment-backed authentication branch and stop the login TUI router from treating environment configuration as an explicit CLI secret.
- Retire the pre-migration `resolve_secrets_channel` compatibility wrapper and make the channel-specific stdin and descriptor readers private implementation details behind `read_machine_secret_payload`.
- Remove the obsolete callback-free login classification test and route secure-input tests through the canonical selector and reader.
- Refresh login refusal assertions and prose to describe only the paired explicit channels while preserving substrate settings used outside CLI secret discovery.
- Run focused secure-input, login frontend, profile-password, profile-creation, help, and startup tests plus scoped lint, type, import, and negative-symbol checks.

## Outcome

The CLI now has no environment-backed scalar-secret bypass at the profile-session gate and no exported compatibility reader or selector shim. Login routing depends only on an explicit machine channel, output mode, terminal capability, and profile availability. All five closed-inventory commands retain the canonical selector, reader, and hardened prompt; no prompt or machine-secret reader exists outside that inventory. Core settings and storage-substrate configuration remain intact for separately governed programmatic callers.

## Notes

The shared worktree contained unrelated registry, command-spec migration, locale, generated-metadata, and prior execution-record changes. They were preserved and excluded from this step. Generated metadata remediation remains intentionally open for its owning step and was not modified here.
