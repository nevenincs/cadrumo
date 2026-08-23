---
tags:
  - '#plan'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_hash: 'sha256:c0d987c6e4e25b8caa2c0bf69005ee4e36bc4989a8e927449bcdd0468ede7efe'
tier: L3
related:
  - '[[2026-08-23-cli-machine-secret-channel-unification-adr]]'
  - '[[2026-08-23-cli-machine-secret-channel-unification-global-machine-secret-contract-research]]'
---

<!-- RETIRED: P10 -->

# `cli-machine-secret-channel-unification` plan

## Description

Unify every scalar-secret CLI command behind one canonical, machine-operable input contract. Both `--secrets-stdin` and `--secrets-fd` become uniform wherever applicable; obsolete command-local readers, CLI environment fallbacks, legacy payload fields, and duplicated declarations are removed rather than retained as compatibility surface.

## Steps

## Wave `W01` - Canonical machine-secret capability

Establish one strict transport capability and one closed inventory before migrating commands.

### Phase `W01.P01` - Canonical transport primitives

Build the reusable parser, selector, option declarations, and descriptor reader.

- [x] `W01.P01.S01` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and build the shared strict frozen payload base, reusable Typer option annotations, typed selection result, conflict-before-read selector, and bounded one-shot reader while retaining fd0, refusing negative descriptors and fd1/fd2, and deleting old helpers atomically after migration; `src/cadrumo/entrypoints/cli/_config/_secure_input.py`.
- [x] `W01.P01.S02` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and prove aliases, defaults, order, help, strict parsing, size bounds, descriptor refusal and closure, one-shot reads, and secret-free errors for the canonical capability; `src/cadrumo/entrypoints/cli/_config/tests/test_secure_input_machine_channels.py`.

### Phase `W01.P02` - Closed inventory and safe discovery

Define the authoritative adopter inventory and value-free metadata contract.

- [x] `W01.P02.S03` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and define the exact five-command machine-secret inventory, command-model registration, safe field and type schemas, conditional restore variants, and conformance API; `src/cadrumo/entrypoints/cli/_machine_secret_contract.py`.
- [x] `W01.P02.S04` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and project value-free machine-secret payload variants into verb input and command schemas; `src/cadrumo/entrypoints/cli/_verb_input_schema.py and src/cadrumo/entrypoints/cli/_command_schema.py`.
- [x] `W01.P02.S05` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and prove exact inventory membership, single identical flag declarations across help, Click, metadata, and schema, safe field types without values, and no outside adopters; `src/cadrumo/entrypoints/cli/tests/test_machine_secret_metadata.py`.

## Wave `W02` - Atomic verb migration and hard cut

Move all scalar-secret verbs to the capability and delete obsolete routes and names.

### Phase `W02.P03` - Profile establishment and proof

Migrate login and profile creation while preserving policy and mutation ordering.

- [x] `W02.P03.S06` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate config login to both canonical explicit channels and explicit prompt or refusal while deleting CLI environment, settings, keyring, substrate fallthrough, and local transport branches; `src/cadrumo/entrypoints/cli/_config/_custody.py`.
- [x] `W02.P03.S07` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate profile creation to both canonical channels, remove manual injection and CLI environment fallback, and preserve confirmation, policy, lazy materialization, and mutation order; `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py and src/cadrumo/entrypoints/cli/_config/_manager_dispatch.py`.

### Phase `W02.P04` - Rotation, recovery, and certificate custody

Migrate remaining scalar-secret commands and hard-cut legacy fields.

- [x] `W02.P04.S08` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate passphrase rotation to the shared capability and canonical payload model; `src/cadrumo/entrypoints/cli/_config/_passphrase.py`.
- [x] `W02.P04.S09` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and migrate restore to two conditional canonical payload variants and hard-cut the legacy password field in favor of passphrase; `src/cadrumo/entrypoints/cli/_config/_restore_cli.py`.
- [x] `W02.P04.S10` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and add descriptor input to certificate-secret storage through the shared capability and hard-cut secret in favor of certificate_passphrase; `src/cadrumo/entrypoints/cli/_config/_certificate.py`.

### Phase `W02.P05` - Locale alignment and obsolete-code purge

Align diagnostics and remove superseded implementations and fallbacks.

- [x] `W02.P05.S11` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and regenerate all four locales through python -m dev.locales with channel-neutral diagnostics that reserve only fd1/fd2 and remove stale environment and legacy-field strings; `src/cadrumo/locales/ and dev/locales/`.
- [x] `W02.P05.S12` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and remove obsolete imports, models, manual injection, CLI environment routes, direct readers, and prompts outside the closed inventory while retaining separately governed core and programmatic settings; `src/cadrumo/entrypoints/cli/ and its tests`.

### Phase `W02.P11` - Root profile authentication precondition

Restore self-authenticating custody grammar and add explicit keychain-free per-invocation profile proof with dispatch-wide source safety.

- [x] `W02.P11.S19` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and restore config passphrase change as the sole three-field rotation verb with canonical leaf transport, public metadata, tests, and an explicit self-authenticating root-gate exemption; `passphrase command specification handler metadata and tests`.
- [x] `W02.P11.S20` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and define the distinct root profile-authentication option pair, strict profile_passphrase payload, typed command-graph posture, value-free metadata, and universal non-adopter invariants; `root command specification secure input contract metadata and tests`.
- [x] `W02.P11.S21` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and implement parsed-dispatch root and leaf source preflight, exact-target login fallback, show validate and history gate convergence, unused-source refusal, target assertions, bounded cleanup, and non-secret persistence warning; `root CLI gate profile target routing session integration and focused tests`.
- [x] `W02.P11.S22` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and align all four locales and focused behavior tests for root applicability, parse precedence, session refusal reasons, collisions, self-authenticating exemptions, cleanup, leakage, and Windows descriptor bootstrap semantics; `CLI locale sources root profile-authentication tests and platform bootstrap`.

## Wave `W03` - Runtime, generated, and operator proof

Prove real machine operation and align generated and user-facing surfaces.

### Phase `W03.P06` - Real subprocess matrix

Exercise both transport channels and refusal behavior through actual processes.

- [x] `W03.P06.S13` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and add real subprocess success coverage for stdin and inherited descriptors across all five leaf commands and both restore doors plus keychain-free root profile authentication on representative read and write commands, certificate dual-source combinations, fd0, closure, prompt absence, Windows HANDLE bootstrap, and leak checks; `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`.
- [ ] `W03.P06.S14` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and extend the real subprocess matrix with same-scope and cross-scope conflict before read and mutation, invalid descriptor and payload cases, size bounds, old-field refusal, hostile-environment non-interference, valid-session non-consumption, wrong or absent target refusal, self-authenticating exemptions, prompt-only TTY behavior, and four-locale snapshots; `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`.

### Phase `W03.P07` - Generated surfaces and operator documentation

Regenerate machine metadata and document the uniform contract.

- [x] `W03.P07.S15` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and project and regenerate safe conditional leaf machine-secret metadata and root profile_authentication posture across registration metadata, command schemas, CLI tree artifacts, and their tests; `dev/quality/generate_command_registration_metadata.py and generated CLI metadata artifacts`.
- [x] `W03.P07.S16` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and update operator documentation and sequence sources through canonical generators to describe both leaf channels, the distinct root profile-authentication pair, cross-scope collision rules, caller-owned descriptors, Windows HANDLE bootstrap, repeated keychain-free Argon2 work, bounded-lifetime cleanup, and removed CLI environment fallback; `docs/how-to and docs/reference CLI secret-input documentation and sequences`.

## Wave `W04` - Closure

Run structural assurance, review, and Vault reconciliation before declaring completion.

### Phase `W04.P08` - Structural gates

Run focused and broad verification and prove obsolete paths are absent.

- [ ] `W04.P08.S17` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and run focused and broad lint, type, import, test, subprocess, metadata, locale, generator, documentation, sequence, Sphinx, obsolete-code census, and Vault gates while recording honest triage for unrelated failures; `feature-scoped source tests generated documentation and Vault records`.

### Phase `W04.P09` - Independent assurance

Review, remediate, audit honestly, and reconcile the feature corpus.

- [ ] `W04.P09.S18` - Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and perform formal code review, remediate all high and critical findings, execute a fresh-context honesty audit, reconcile ADR, research, plan, indexes, and summaries, and close all eighteen Steps only with durable evidence; `feature implementation and Vault lifecycle documents`.

## Parallelization

W01 is foundational. S01 precedes S02 and every command migration; S03 precedes metadata work and migration closure. After S01 and S03, S06-S10 may proceed in parallel only with exclusive module ownership, with S07 owning both dynamic profile-creation files. S11-S12 follow the leaf migrations. The reviewed keychain-free amendment executes S19, then S20, then S21; S22 follows their settled behavior. S04 may proceed after S03, while S05 and S15 wait for declarations to settle. Runtime matrices S13-S14 follow S07, S12, and S19-S22. S15 follows all declarations and runtime posture; S16 follows S15. S17 and S18 are strictly sequential closure work.

## Verification

Completion requires real subprocess proof for stdin and inherited descriptors across all five leaf commands, both restore variants, and keychain-free root authentication on representative profile-bound reads and writes; same-scope and cross-scope conflict-before-read and conflict-before-mutation proof; exact-target and self-authenticating exemptions; bounded strict parsing, honest cleanup, POSIX descriptor and Windows HANDLE-bootstrap lifecycle tests; four-locale diagnostics; exact help, Click, metadata, and generated-schema parity; hostile-environment non-interference; removal censuses for obsolete fields and paths; focused and broader quality gates; formal sol architecture and code review; fresh-context honesty audit; and final Vault reconciliation. No Step may be marked complete without recorded evidence.
