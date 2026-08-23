---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e19a86b20e54017794c05215c8d4f8b30c1bc598aaf82060e0c664cb6ca69067'
step_id: 'S07'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate profile creation to both canonical channels, remove manual injection and CLI environment fallback, and preserve confirmation, policy, lazy materialization, and mutation order

## Scope

- `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py and src/cadrumo/entrypoints/cli/_config/_manager_dispatch.py`

## Description

- Ground profile creation in the accepted ADR, research, live command-spec registry, scripted registration door, and canonical secure-input capability.
- Register `_CreationSecrets` as the strict canonical `passphrase` payload model.
- Route both explicit machine channels through `select_machine_secret_channel` and `read_machine_secret_payload` before any profile mutation.
- Remove settings and environment passphrase fallback while retaining verified-terminal prompts and confirmation refusal.
- Extend the lazy profile-create command spec with one `--secrets-fd` declaration beside the existing stdin declaration.
- Prove explicit stdin creation, fd reading and closure, hostile configured-secret non-interference, lazy help/schema parity, policy refusal, fact ordering, and real encrypted creation.

## Outcome

Profile creation now accepts the canonical paired machine-secret channels and refuses their conflict before reading. Its payload inherits the shared strict frozen base and is registered against the closed inventory. Non-interactive creation no longer reads configured or environment passphrases implicitly. Field projection remains before secret consumption and registration, and the existing spec-driven lazy materialization remains intact without signature injection.

## Notes

The installed `vaultspec-rag` client initially refused discovery because it was version 0.4.1 against a 0.4.2 service; a one-shot 0.4.2 client completed semantic grounding, paired with exact `rg` and current-tree reads. The post-plan command-spec refactor had already removed manual signature injection and moved option ownership into `_profile_command_specs`; the implementation therefore preserved that architecture and changed only `_WIZARD_CREATE_PARAMETERS` there.

Focused Ruff and 36 profile-create, manager-routing, command-spec, and secure-input tests passed. An additional integration checkpoint passed 25 of 27 tests; its two failures concern the concurrently modified root error-envelope command identifier, outside this Step and absent from its scoped diff. Focused static analysis reported only existing private-use and unknown-wrapper findings in the unchanged manager dispatch/common boundary. No data was deleted and no compatibility scaffold was added.
