---
tags:
  - '#adr'
  - '#rust-component-provisioning'
date: '2026-10-26'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:373fa25c859c5d53d6bf9ffdcaa2986b9ded3fb5e8a19de96c32ef8b52ab4d76'
related:
  - "[[2026-10-24-rust-component-provisioning-adr]]"
  - '[[2026-10-24-rust-component-provisioning-audit]]'
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-11-mcp-parity-full-parity-adr]]'
  - '[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]'
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-10-10-mcp-parity-parity-mechanism-adr]]'
  - '[[2026-10-27-rust-component-provisioning-human-review-authority-adr]]'
---
# `rust-component-provisioning` adr: `Component setup as registered operations` | (**status:** `accepted`)

## Problem Statement

The CLI, TUI and MCP read component status and set up the browser by launching the `components` role through `src/cadrumo/adapters/outbound/components/client.py` (`provision_cli.py`, `tui/setup/door.py`, `tui/setup/screen.py`, `cadrumo_mcp/mcp/component_setup.py`, `diagnostics_repair_composition.py`). These calls bypass the registered-operation supervisor, so they have no journal, runtime admission, review bearer or effect accounting. The full-screen gate `dev/operation_contract_manifest/tests/test_operation_catalogue.py:601` rejects direct adapter access from the TUI setup screen.

Basis: the owner's first-hand rulings require registered operations in a signed-in profile session and human-only setup approval.

## Considerations

- The supervisor already carries what setup needs: a digest-bound REVIEW checkpoint (`application/operations/supervisor_context.py:51`, `interactions.py:152`), typed phase, progress and notice events (`owner.py:72`), owned process resources and UNKNOWN on owner loss (`_supervisor_reconciliation.py:75`).
- The ledger LLM review and `user-profile.censo-review` are working REVIEW operations end to end across CLI, TUI and MCP (`llm_review_operation.py:145`, `censal_operation.py:488`).
- Surface gaps: the TUI operation modal drops progress figures (`tui/operations/logs.py:133`), no CLI command consumes operation events, and MCP relays progress only on `observe`.
- Every progress event is a journal write, and notices carry only codes.
- Registered operations bind the exact signed-in profile and session (`src/cadrumo_runtime/host/profile_connection_operations.py:284`). Component files remain installation-wide; the profile session supplies operation admission, the journal, review and human checks.

## Considered options

- **Registered operations for status, verify, setup and remove.** Chosen by the owner: one admission, journal and review path for every surface.
- **A TUI-only composition seam.** Rejected: it satisfies the gate's letter, but CLI and MCP stay outside the supervisor.
- **Deferral with a recorded finding.** Rejected: it leaves a failing gate and an unjournaled network write.

## Constraints

1. The operations are `config.provision.status` (journaled read, local), `config.provision.verify` (full check with progress, network read), `config.provision.setup` (resumable, one REVIEW, exact approval, effects NONE, UPDATED and UNKNOWN, owns the role process, network write) and `config.provision.remove` (recorded update, local write). Browser setup is `setup` naming the browser. The local status operation always requests the quick check. Full status and verify use `config.provision.verify` for network-read admission and invoke the native role as `status --full`; both native full-check commands share the same engine behavior. CLI probe and verify retain their distinct rendering and exit rules. Cancelling is the supervisor's operation cancellation.
2. The setup executor plans through the role and publishes the plan as its review operand. The reviewed digest is the role's `plan_digest`. Apply runs the role's setup approving exactly that digest. Reject settles NONE. A plan that changed between review and apply is a refusal that asks for a new run.
3. The executor marks the effect UNKNOWN before it approves the role's setup and settles from the role's outcome. An undeterminable outcome stays UNKNOWN.
4. Role phases, byte progress and notices relay as operation phase, progress and notice events. Progress is throttled.
5. The local AI stays read-only on every Python surface, as amendment 2026-10-26 of `2026-10-24-rust-component-provisioning-adr` rules.
6. The components client and protocol are reached only through one entrypoints composition module. No frontend imports them.
7. `config.provision.status`, `config.provision.verify`, `config.provision.setup` and `config.provision.remove` bind the signed-in profile's session and journal. A review remains bound to that admitted invocation; only an authenticated human surface holding current runtime-issued response authority may apply or reject it. For `config.provision.setup` only, a separately authenticated HUMAN session on the same exact active profile may explicitly claim the current REVIEW through the runtime while its original invocation admission and execution lease remain live, under the exact bindings and retirement rules of `2026-10-27-rust-component-provisioning-human-review-authority-adr`. This grants only current REVIEW response authority and does not transfer the operation's admission or ownership. Before sign-in, the CLI and TUI tell the person to sign in first. The desktop keeps provisioning through its in-process Rust engine without a signed-in profile.
8. The setup review requires a human answer. An MCP session is always an agent's provider run, and the MCP service has no knowledge of which provider runs it, so no MCP session answers the review: MCP may start and observe a setup, and a person explicitly claims and answers its current review from the desktop, TUI or CLI. Runtime admission verifies the human responder separately from MCP invocation provenance and refuses every MCP claim, response-authority inspection, APPLY and REJECT, including the original MCP submitter. The claim is bound to the exact current operation, interaction, revision, proposal, human connection/session, profile, boot and authority generation; observation and reattachment grant nothing. The journal separately attributes the verified human claim and decision.

## Implementation

We will register the four profile-bound operations in one entrypoints composition group, with their access facts, result and review projections and phase codes. Each surface becomes a client; the CLI and TUI require sign-in before submitting:
- The CLI submits through `run_registered_operation`, with a review handler that prompts or takes `--yes` and an event consumer drawing progress.
- The TUI uses the operation modal, which gains a progress row, and the setup door is deleted.
- MCP drops its four setup tools for the generic execute and observe tools; it never responds to the setup review.
- The repair report and the MCP setup gate read status through the status operation.
- The desktop retains its native provisioning path before sign-in. For a profile-bound setup started elsewhere, its verified person relay exposes the same explicit current-review claim and answer action.
- CLI and TUI also expose an explicit human review/claim/answer action for a known setup operation. The provisioning-only runtime claim and broker actor assignment follow `2026-10-27-rust-component-provisioning-human-review-authority-adr`; other operation response guards remain unchanged.

## Rationale

Registered operations give status reads and the browser download the runtime admission, journal, review bearer and effect accounting used by other CLI, TUI and MCP submissions. Binding their execution to a signed-in profile reuses the runtime's admitted operation lifetime. It does not put installation-wide public component files in encrypted profile custody or change the desktop's native path.

## Consequences

- Setup and status use the signed-in profile's admission and journal; setup gains a durable human review.
- CLI and TUI component operations require sign-in. Native desktop provisioning remains available before sign-in.
- Plan drift between review and apply becomes a visible refusal.
- Status reads become journaled operations, which costs time on frequently refreshed surfaces.
- The TUI modal and the CLI gain progress rendering, and MCP loses its special setup tools.
- Reconsider if a surface needs a status read that the operation's journaling makes too slow.
