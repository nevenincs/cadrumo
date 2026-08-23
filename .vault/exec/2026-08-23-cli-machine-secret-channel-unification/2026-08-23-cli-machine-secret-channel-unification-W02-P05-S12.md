---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f62cac055795c58dabf9b386c4992d7da5dcd26522c8e88cba0c83f48bc8f767'
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
- Correct the post-S12 inventory regression by treating the closing-authority bundle as a typed structured document: require the canonical `--file` input, validate directly as `InventoryClosingAuthorityRecord`, and remove the bespoke stdin/fd secret-channel wrapper.
- Add an exact conformance census that confines public scalar-secret APIs to the five authorized leaves and the distinct root authentication gate.
- Remove the profile-readiness helper's duplicate session resume; profile record reads now require the exact live session established by the parsed root gate.
- Replace the obsolete ambient-passphrase CLI regression with a refusal contract and remove stale prose without removing separately governed non-CLI substrate configuration.
- Run focused secure-input, login frontend, profile-password, profile-creation, help, and startup tests plus scoped lint, type, import, and negative-symbol checks.

## Outcome

The CLI now has no environment-backed scalar-secret bypass at the profile-session gate and no exported compatibility reader or selector shim. Login routing depends only on an explicit machine channel, output mode, terminal capability, and profile availability. All five closed-inventory commands retain the canonical selector, reader, and hardened prompt, while the distinct root gate owns its explicitly declared profile-authentication source. The inventory closing-authority bundle is validated as its canonical typed domain document from a required file and no longer consumes scalar-secret APIs. Profile readiness no longer attempts a second session resume. Core settings and storage-substrate configuration remain intact for separately governed programmatic callers, but cannot silently authenticate a CLI invocation.

## Notes

The shared worktree contained unrelated registry, command-spec migration, locale, generated-metadata, and prior execution-record changes. They were preserved and excluded from this step. Generated metadata remediation remains intentionally open for its owning step and was not modified here.

The ambient CLI gate bypass was removed because environment configuration is neither an explicit per-invocation authority nor a safe machine-secret carrier. Retaining `Settings` and application-level passphrase resolution is intentional: those are separately governed programmatic/storage-substrate capabilities and are not consulted by the CLI authentication gate. Exact AST and `rg` censuses prove the public secret selector, reader, payload, staging, and prompt APIs remain confined to the five scalar-secret leaves plus the distinct root profile-authentication contract/gate.

Landing evidence: 37 focused secret-contract, root-gate, and command-spec unit tests passed; 34 focused inventory, delegated-authority, root-session, and ambient-refusal integration tests passed; scoped Ruff and ty checks passed. The four-locale exact census found the canonical authority-file key in every locale and no retired authority stdin/fd keys. The repository-wide locale audit remains non-green on its pre-existing thousands-of-keys backlog outside this step's CLI locale surface; no unrelated locale material was absorbed.
