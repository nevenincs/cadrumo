---
tags:
  - '#research'
  - '#tui-entrypoint-separation'
date: '2026-09-08'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:8955e84c7842ae207c7e65d276006def94c5d5cada3e93b5ff7fd5a9fd2050e7'
related:
  - "[[2026-08-11-tui-interface-adr]]"
---

# `tui-entrypoint-separation` research: `command capability decoupling`

The existing global `--tui` request treats command-graph metadata as a TUI routing authority. That makes CLI availability and TUI reachability one hand-maintained fact, despite the transports being sibling entrypoints. The implementation can be reduced to a dedicated launcher command and the entrypoint boundary can remain out-of-process, but the target command spelling and replacement authority must be settled before the accepted mappings, gates, and plan rows are changed.

## Findings

### The command graph currently owns TUI reachability

`TuiCapability` is a two-value enum on every `CommandSpec`, defaulted to `NOT_IMPLEMENTED`; five CLI nodes are manually marked `AVAILABLE`. `src/cadrumo/entrypoints/cli/command_spec.py:732`; `src/cadrumo/entrypoints/cli/_root_command_specs.py:44`; the former source file; `src/cadrumo/entrypoints/cli/config/_custody_command_specs.py:137`; `src/cadrumo/entrypoints/cli/config/_profile_inventory_specs.py:70`.

The option is not passive metadata. The root captures `--tui`, the runtime enforces it before executable leaves, and `_tui_policy` selects refusal versus full-screen routing. `src/cadrumo/entrypoints/cli/_root_command_specs.py:127`; `src/cadrumo/entrypoints/cli/_root_cli.py:29`; `src/cadrumo/entrypoints/cli/_command_runtime.py:184`; the former source file.

### Removing the mapping has defined consumers beyond the CLI

The modelo action denominator consumes `TuiCapability`, so deleting the field without changing the gate would either break the development surface or retain the same false coupling under another name. The global-request tests assert the complete available set and TUI tests assert the current request spelling. the former source file; the former source file; `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py:57`.

Modelo select/review and profile-manager paths also branch on the root request and open destination sessions. A complete separation must remove or relocate those destination-routing branches, not merely turn the capability values off. `src/cadrumo/entrypoints/cli/_modelo_work_select_cli.py:57`; `src/cadrumo/entrypoints/cli/_modelo_work_review_cli.py:20`; `src/cadrumo/entrypoints/cli/config/_manager_dispatch.py:63`.

### A dedicated launcher already has an import-safe implementation path

The CLI launches the TUI as a child interpreter through a shared entrypoint protocol; it does not import the TUI package. That launcher can be a narrow dedicated-command handler provided command-specific destination routing does not remain in the CLI. the former source file; the former source file.

The active CLI boundary permits only `config` and `app` at the root. Consequently, `aeat tui` is outside the live command contract; `aeat app tui` is the compatible dedicated command form. A root-level `tui` family is an alternative only if its separate root-hierarchy authority and the project rule are amended first. `.codex/rules/aeat-cli-contract.md`; `.codex/rules/aeat-architecture-boundaries.md`; `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:206`.

### The request reverses accepted decisions, not only the active modelo plan

The accepted TUI interface, architecture, and modelo-workspace decisions require the global option and command capability mapping. The out-of-process protocol decision remains relevant because the requested separation preserves a process boundary rather than authorising an import. The active `tuimodelo` plan only defers relocation of the mapping, so it cannot resolve its removal on its own. `.vault/adr/2026-08-11-tui-interface-adr.md:62`; `.vault/adr/2026-08-11-tui-architecture-adr.md:1096`; `.vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md:745`; `.vault/adr/2026-09-02-tui-architecture-out-of-process-destination-protocol-adr.md`; `.vault/plan/2026-09-07-tuimodelo-plan.md:73`.

The evidence supports three options for the ADR to decide: retain the global mapping; replace it with a dedicated `aeat app tui` launcher and TUI-owned reachability; or add an `aeat tui` root family after separately changing the root contract. The first retains the coupling the request identifies. The last expands the public command hierarchy. The middle option removes the duplicate authority while retaining the current root rule.

## Sources

- `src/cadrumo/entrypoints/cli/command_spec.py:732`
- `src/cadrumo/entrypoints/cli/_root_command_specs.py:44`
- `src/cadrumo/entrypoints/cli/_root_cli.py:29`
- `src/cadrumo/entrypoints/cli/_command_runtime.py:184`

- `src/cadrumo/entrypoints/cli/_modelo_work_select_cli.py:57`
- `src/cadrumo/entrypoints/cli/_modelo_work_review_cli.py:20`
- `src/cadrumo/entrypoints/cli/config/_manager_dispatch.py:63`

- `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py:57`

- `.codex/rules/aeat-cli-contract.md`
- `.codex/rules/aeat-architecture-boundaries.md`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:206`
- `.vault/adr/2026-08-11-tui-interface-adr.md:62`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:1096`
- `.vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md:745`
- `.vault/adr/2026-09-02-tui-architecture-out-of-process-destination-protocol-adr.md`
- `.vault/plan/2026-09-07-tuimodelo-plan.md:73`
