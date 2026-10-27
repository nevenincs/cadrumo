---
tags:
  - '#plan'
  - '#rust-component-provisioning'
date: '2026-10-26'
tier: L1
related:
  - '[[2026-10-26-rust-component-provisioning-registered-operations-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
modified: '2026-10-27'
body_schema: body-v2
body_hash: 'sha256:e1a848ec2062897bd558db896886f4e9608ca538f89e5f9cd8a7ecf347138bcd'
---

# `rust-component-provisioning` plan

Run component status, verify, setup and removal as registered operations, with the CLI, TUI and MCP as their clients.

## Description

Approved 2026-10-26. Authorization basis: the owner's first-hand approval of registered operations and human-only setup review, with the signed-in-profile execution scope confirmed in the current work instruction. MCP may start and observe setup and never answers its review.

`2026-10-26-rust-component-provisioning-registered-operations-adr` governs every Step; `2026-10-24-rust-component-provisioning-adr` keeps the engine, role and desktop-only local AI rulings. The local AI stays read-only on every Python surface. The framework already has the review checkpoint, typed events, owned process resources and UNKNOWN on owner loss; the gaps are a signed-in profile binding with human review and effect accounting, the TUI modal's progress row, a CLI event consumer, and throttled progress.

## Steps

- [ ] `S01` - Register config.provision.status, verify, setup and remove as registered operations in one entrypoints composition group, bound to the signed-in profile's session, journal, review and human checks, with access facts, typed result and review projections and phase codes. The setup executor owns the role process, reviews the role's plan with its exact plan_digest, marks UNKNOWN immediately before setup --approve <digest>, settles from the role's outcome, throttles progress and polls cancellation. Only a human answers setup review, CLI and TUI require sign-in first, and the desktop keeps native provisioning without a profile; `src/cadrumo/entrypoints/components_operation_composition.py, src/cadrumo/application/components_operations.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/application/operations/access_facts.py`.
- [ ] `S02` - Make the CLI a client of the four operations: provision status, probe, verify, setup, browser and remove submit through run_registered_operation with a review handler that prompts or takes --yes and an event consumer that draws progress, the repair report reads the status operation, and the command table and contract manifest are regenerated; `src/cadrumo/entrypoints/cli/config/provision_cli.py, src/cadrumo/entrypoints/diagnostics_repair_composition.py, src/cadrumo/entrypoints/cli/command_operation_table.py, src/cadrumo/_data/operations/contract_manifest.json`.
- [ ] `S03` - Make the TUI a client of the operations: give the operation modal a progress row, drive setup through the operation controller and modal review, back the setup status port with the status operation, and delete the setup door; `src/cadrumo/entrypoints/tui/operations/modal.py, src/cadrumo/entrypoints/tui/operations/logs.py, src/cadrumo/entrypoints/tui/setup/screen.py, src/cadrumo/entrypoints/tui/setup/door.py, src/cadrumo_runtime/host/frontend/tui/runtime_workbench.py`.
- [ ] `S04` - Make MCP a client of the operations: delete the four setup tools, start and observe setup through the generic tools without ever answering its review, and gate setup actions on the status operation; `src/cadrumo_mcp/mcp/component_setup.py, src/cadrumo_mcp/mcp/progress_relay.py, src/cadrumo_mcp/mcp/runtime_adapter.py, src/cadrumo_mcp/mcp/surfaces.py, src/cadrumo_mcp/mcp/protocol_contract.py`.
- [ ] `S05` - Gate that only the components composition module imports the components client, prove the full-screen adapter gate and the human-only review across surfaces, and update the docs and generated CLI reference; `dev/operation_contract_manifest/tests/test_operation_catalogue.py, dev/quality/tests/test_no_python_provisioning.py, docs/workstation-setup.md, docs/cli/config/provision.rst`.

## Parallelization

S01 lands first. S02, S03 and S04 each depend only on S01 and own disjoint files, so they may run in parallel. S05 is last.

## Verification

- `dev/operation_contract_manifest/tests/test_operation_catalogue.py::test_no_full_screen_surface_reaches_an_outbound_adapter_directly` passes, and a new gate shows only the components composition module imports the components client, each catching an isolated defect.
- Each operation is tested through the real supervisor: a reviewed setup applies exactly the reviewed digest, a rejected one settles NONE, a changed plan refuses, an uncertain outcome stays UNKNOWN, and an MCP session cannot answer the review.
- CLI, TUI and MCP tests drive the operations. CLI and TUI component operations require sign-in and give sign-in guidance before a profile session is active; native desktop provisioning remains available without a profile.
- `just check-import-boundaries`, `check-style`, `check-format`, `check-types` and the operation contract manifest check pass. Tests run as focused paths only, never full suites.
