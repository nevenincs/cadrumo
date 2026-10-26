---
tags:
  - '#plan'
  - '#rust-component-provisioning'
date: '2026-10-26'
tier: L1
related:
  - '[[2026-10-26-rust-component-provisioning-registered-operations-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
modified: '2026-10-26'
body_schema: body-v2
body_hash: 'sha256:5ea8652dcbe91ff7e76785728a86c40d7512a082d43b077922187dc56335a261'
---

# `rust-component-provisioning` plan

Run component status, verify, setup and removal as registered operations, with the CLI, TUI and MCP as their clients.

## Description

Approved 2026-10-26. Basis: the owner's first-hand answers in conversation: registered operations over a TUI-only seam or deferral, "sure" to `2026-10-26-rust-component-provisioning-registered-operations-adr` with its machine scope and human-only review, and the clarification that an MCP session is always an agent's provider run whose provider the MCP service cannot know, so MCP never answers the setup review.

`2026-10-26-rust-component-provisioning-registered-operations-adr` governs every Step; `2026-10-24-rust-component-provisioning-adr` keeps the engine, role and desktop-only local AI rulings. The local AI stays read-only on every Python surface. The framework already has the review checkpoint, typed events, owned process resources and UNKNOWN on owner loss; the gaps are a machine binding with review and commit, the TUI modal's progress row, a CLI event consumer, and throttled progress.

## Steps

- [ ] `S01` - Register config.provision.status, verify, setup and remove as machine-scoped registered operations in one entrypoints composition group: a machine binding without a signed-in profile, access facts, result and review projections, phase codes, a setup executor that owns the role process, publishes the role's plan as a digest-bound review, marks UNKNOWN before approving and settles from the role's outcome, relays throttled progress and polls cancellation, with a human-only review; `src/cadrumo/entrypoints/components_operation_composition.py, src/cadrumo/application/components_operations.py, src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/application/operations/access_facts.py`.
- [ ] `S02` - Make the CLI a client of the four operations: provision status, probe, verify, setup, browser and remove submit through run_registered_operation with a review handler that prompts or takes --yes and an event consumer that draws progress, the repair report reads the status operation, and the command table and contract manifest are regenerated; `src/cadrumo/entrypoints/cli/config/provision_cli.py, src/cadrumo/entrypoints/diagnostics_repair_composition.py, src/cadrumo/entrypoints/cli/command_operation_table.py, src/cadrumo/_data/operations/contract_manifest.json`.
- [ ] `S03` - Make the TUI a client of the operations: give the operation modal a progress row, drive setup through the operation controller and modal review, back the setup status port with the status operation, and delete the setup door; `src/cadrumo/entrypoints/tui/operations/modal.py, src/cadrumo/entrypoints/tui/operations/logs.py, src/cadrumo/entrypoints/tui/setup/screen.py, src/cadrumo/entrypoints/tui/setup/door.py, src/cadrumo_runtime/host/frontend/tui/runtime_workbench.py`.
- [ ] `S04` - Make MCP a client of the operations: delete the four setup tools, start and observe setup through the generic tools without ever answering its review, and gate setup actions on the status operation; `src/cadrumo_mcp/mcp/component_setup.py, src/cadrumo_mcp/mcp/progress_relay.py, src/cadrumo_mcp/mcp/runtime_adapter.py, src/cadrumo_mcp/mcp/surfaces.py, src/cadrumo_mcp/mcp/protocol_contract.py`.
- [ ] `S05` - Gate that only the components composition module imports the components client, prove the full-screen adapter gate and the human-only review across surfaces, and update the docs and generated CLI reference; `dev/operation_contract_manifest/tests/test_operation_catalogue.py, dev/quality/tests/test_no_python_provisioning.py, docs/workstation-setup.md, docs/cli/config/provision.rst`.

## Parallelization

S01 lands first. S02, S03 and S04 each depend only on S01 and own disjoint files, so they may run in parallel. S05 is last.

## Verification

- `dev/operation_contract_manifest/tests/test_operation_catalogue.py::test_no_full_screen_surface_reaches_an_outbound_adapter_directly` passes, and a new gate shows only the components composition module imports the components client, each catching an isolated defect.
- Each operation is tested through the real supervisor: a reviewed setup applies exactly the reviewed digest, a rejected one settles NONE, a changed plan refuses, an uncertain outcome stays UNKNOWN, and an MCP session cannot answer the review.
- CLI, TUI and MCP tests drive the operations; status works with no signed-in profile.
- `just check-import-boundaries`, `check-style`, `check-format`, `check-types` and the operation contract manifest check pass. Tests run as focused paths only, never full suites.
