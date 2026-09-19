---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:03fb82917f3165c10e038f315c8d610e707b01f00b3ebd138f1d47b1e1909655'
step_id: 'S20'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and define the distinct root profile-authentication option pair, strict profile_passphrase payload, typed command-graph posture, value-free metadata, and universal non-adopter invariants

## Scope

- `root command specification secure input contract metadata and tests`

## Description

- Declare exactly one `--profile-secrets-stdin` and one `--profile-secrets-fd` on the executable root through immutable command specification authority.
- Add a distinct root channel kind, strict `profile_passphrase` payload specification and model, parse-only source options, selection type, and root-scoped diagnostic namespace while reusing the canonical bounded reader.
- Derive each executable leaf's `profile_authentication` posture from its parsed command graph node, explicit self-authentication posture, and the typed bootstrap-exemption authority.
- Project the value-free payload field, canonical 8 KiB bound, same-scope exclusivity, and cross-scope collision rules into registration metadata.
- Gate the exact root pair, leaf-only five-command `MachineSecretSpec` inventory, scope disjointness, strict frozen `SecretStr` behavior, live Click declarations, graph-derived posture, metadata safety, and non-consumption on help, version, bare, unknown, and parse-failure surfaces.

## Outcome

The root profile-authentication capability is a distinct typed scope and does not expand the closed five-leaf machine-secret inventory. S21 can consume `ProfileSecretSourceOptions`, `profile_authentication_posture`, `select_profile_secret_channel`, and `read_profile_secret_payload` after Click resolves an executable leaf; S20 deliberately performs no root source read, collision preflight, authentication, or dispatch mutation.

Focused Ruff and scoped `ty` passed. Fifty-two combined root/spec/metadata/secure-input/passphrase tests passed before the final live-Click assertion was added, and the final S20 module passed all fourteen cases. Root help, version, bare, unknown-command, and parse-error probes did not parse the staged profile payload. Repository-wide type and import-linter gates retain unrelated existing diagnostics outside the S20 ownership surface; neither identifies a new S20 dependency violation.

Independent SOL review reported no high or critical findings. Its one medium finding identified possible drift between graph payload metadata and the runtime Pydantic model. Remediation added `resolve_profile_secret_model` and `root_profile_secret_model`, which require the deferred graph target to inherit `MachineSecretPayload` and exactly match graph field authority; twenty-six focused contract and universal-invariant tests passed after remediation.

## Notes

Concurrent shared-worktree serialization committed the implementation in `27dff62abe` together with S19 follow-ups and committed this record's scaffold in `783cae1729` before the S20 executor reached its own commit boundary. Shared history was not rewritten or duplicated. S19 remains open because its runtime root-gate exemption is assigned to S21 remediation and is not proven by S20 metadata.
