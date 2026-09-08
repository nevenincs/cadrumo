---
tags:
  - '#plan'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
tier: L2
related:
  - '[[2026-09-08-tui-entrypoint-separation-command-capability-decoupling-research]]'
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-09-02-tui-architecture-out-of-process-destination-protocol-adr]]'
  - '[[2026-09-07-tuimodelo-adapter-migration-adr]]'
modified: '2026-09-08'
body_schema: body-v2
body_hash: 'sha256:e48726caccbf1e28cb20d6040accde8b5fbac4a46141476f57a0a5732c1e54eb'
---

# `tui-entrypoint-separation` plan

Remove CLI-owned TUI reachability while retaining one opaque `aeat app tui` launcher.

## Description

This plan executes the accepted entrypoint-separation amendments. P01 removes the
command-graph mapping; P02 installs the opaque launcher and removes every CLI destination
crossing; P03 proves and publishes the resulting boundary; P04 reconciles the active
modelo campaign's deferred relocation rows. The TUI architecture and interface decisions
govern the process boundary, while the modelo workspace and adapter-migration decisions
govern the removal of modelo-specific coupling.

## Steps

### Phase `P01` - retire CLI-owned TUI policy

Remove the global request, command capability model, and every CLI routing branch so the command graph is scripted-command-only.

- [ ] `P01.S01` - Remove TuiCapability and the per-command capability field from the canonical command specification; `src/cadrumo/entrypoints/cli/command_spec.py`.
- [ ] `P01.S02` - Remove capability arguments and values from the CLI command-spec declaration families; `src/cadrumo/entrypoints/cli command-spec modules`.
- [ ] `P01.S03` - Delete the global TUI request state, enforcement policy, and command-runtime interception; `src/cadrumo/entrypoints/cli root runtime`.
- [ ] `P01.S04` - Remove root help and locale keys that advertise the retired global TUI option; `src/cadrumo/entrypoints/cli root presentation`.

### Phase `P02` - install the opaque root launcher

Expose aeat app tui as the sole launch seam and retire the CLI destination protocol without changing TUI-owned navigation.

- [ ] `P02.S05` - Add the aeat app tui opaque root-launch command to the live command tree; `src/cadrumo/entrypoints/cli root command specifications`.
- [ ] `P02.S06` - Reduce the session bridge to fixed child-process launch and exit-status propagation; `src/cadrumo/entrypoints/cli/_tui_session.py`.
- [ ] `P02.S07` - Remove Modelo selection and review branches that route CLI work into TUI destinations; `src/cadrumo/entrypoints/cli Modelo work handlers`.
- [ ] `P02.S08` - Remove profile-manager dispatch that selects a TUI flow from CLI invocation state; `src/cadrumo/entrypoints/cli/config/_manager_dispatch.py`.
- [ ] `P02.S09` - Retire the shared CLI-to-TUI destination outcome protocol after confirming no non-CLI consumer remains; `src/cadrumo/entrypoints/full_screen_session_protocol.py`.

### Phase `P03` - prove and publish the separated boundary

Replace mapping-based tests with boundary tests and regenerate the affected command reference and locale output.

- [ ] `P03.S10` - Replace global-request tests with command-tree and no-routing boundary tests; `src/cadrumo/entrypoints/cli/tests`.
- [ ] `P03.S11` - Update installed TUI entrypoint tests for the opaque aeat app tui launcher; `src/cadrumo/entrypoints/tui/tests`.
- [ ] `P03.S12` - Regenerate command documentation and locale coverage from the changed live command tree; `dev/docs and src/cadrumo/locales`.
- [ ] `P03.S13` - Add an import and AST boundary gate that refuses any CLI TUI route or capability reference outside the opaque launcher; `dev/quality`.

### Phase `P04` - reconcile inherited modelo plan state

Retire the active plan rows whose only purpose was relocating the removed capability declaration.

- [ ] `P04.S14` - Retire the deferred shared-capability relocation rows through the tuimodelo plan CLI; `.vault/plan/2026-09-07-tuimodelo-plan.md`.

## Parallelization

P01 precedes P02 because the launcher must not coexist with global routing policy.
P02.S07 and P02.S08 can proceed independently after P01; P02.S09 follows their consumer
removal. P03 follows all runtime changes. P04 may run after the amended decisions but
closes only after the replacement boundary tests pass.

## Verification

The live command parser exposes `aeat app tui` and rejects the retired global option.
No CLI module outside the fixed child-process launcher references a TUI route, destination,
capability, or outcome. The TUI root starts through the opaque launcher without a CLI import.
Focused CLI and TUI tests, generated command documentation, locale coverage, and the boundary
gate must pass. A mandatory code review follows each completed implementation Step.
