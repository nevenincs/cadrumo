---
tags:
  - '#adr'
  - '#rust-component-provisioning'
date: '2026-10-26'
modified: '2026-10-26'
body_schema: 'body-v2'
body_hash: 'sha256:d9710346f3b7ed152dcdf071ffa1aa948a4806348b53f29e94ec2b263fab9501'
related:
  - "[[2026-10-24-rust-component-provisioning-adr]]"
  - '[[2026-10-24-rust-component-provisioning-audit]]'
---

# `rust-component-provisioning` adr: `Component setup as registered operations` | (**status:** `accepted`)

## Problem Statement

The CLI, TUI and MCP read component status and set up the browser by launching the `components` role themselves through `src/cadrumo/adapters/outbound/components/client.py` (`provision_cli.py`, `tui/setup/door.py`, `tui/setup/screen.py`, `cadrumo_mcp/mcp/component_setup.py`, `diagnostics_repair_composition.py`). They bypass the registered-operation supervisor that the architecture requires every CLI, TUI and MCP submission to use, so these launches have no journal, runtime admission, review bearer or effect accounting. The full-screen gate `dev/operation_contract_manifest/tests/test_operation_catalogue.py:601` has failed since the TUI setup screen began importing the adapter. On 2026-10-26 the owner chose registered operations over a TUI-only composition seam and over deferral.

Basis: the owner's first-hand answers of 2026-10-26 in conversation: registered operations over a TUI-only seam or deferral, then "sure" to this record with its recommended machine scope and human-only approval.

## Considerations

- The supervisor already carries what setup needs: a digest-bound REVIEW checkpoint (`application/operations/supervisor_context.py:51`, `interactions.py:152`), typed phase, progress and notice events (`owner.py:72`), owned process resources and UNKNOWN on owner loss (`_supervisor_reconciliation.py:75`).
- The ledger LLM review and `user-profile.censo-review` are working REVIEW operations end to end across CLI, TUI and MCP (`llm_review_operation.py:145`, `censal_operation.py:488`).
- Surface gaps: the TUI operation modal drops progress figures (`tui/operations/logs.py:133`), no CLI command consumes operation events, and MCP relays progress only on `observe`.
- Every progress event is a journal write, and notices carry only codes.
- Machine provisioning access binds through a signed-in profile today and grants no review or commit (`local_reader_operation.py:26`).

## Considered options

- **Registered operations for status, verify, setup and remove.** Chosen by the owner: one admission, journal and review path for every surface.
- **A TUI-only composition seam.** Rejected: it satisfies the gate's letter, but CLI and MCP stay outside the supervisor.
- **Deferral with a recorded finding.** Rejected: it leaves a failing gate and an unjournaled network write.

## Constraints

1. The operations are `config.provision.status` (journaled read, local), `config.provision.verify` (full check with progress, network read), `config.provision.setup` (resumable, one REVIEW, exact approval, effects NONE, UPDATED and UNKNOWN, owns the role process, network write) and `config.provision.remove` (recorded update, local write). Browser setup is `setup` naming the browser; the full status is `status` with the full check. Cancelling is the supervisor's operation cancellation.
2. The setup executor plans through the role and publishes the plan as its review operand. The reviewed digest is the role's `plan_digest`. Apply runs the role's setup approving exactly that digest. Reject settles NONE. A plan that changed between review and apply is a refusal that asks for a new run.
3. The executor marks the effect UNKNOWN before it approves the role's setup and settles from the role's outcome. An undeterminable outcome stays UNKNOWN.
4. Role phases, byte progress and notices relay as operation phase, progress and notice events. Progress is throttled.
5. The local AI stays read-only on every Python surface, as amendment 2026-10-26 of `2026-10-24-rust-component-provisioning-adr` rules.
6. The components client and protocol are reached only through one entrypoints composition module. No frontend imports them.
7. The operations bind a machine scope that needs no signed-in profile, under runtime admission and the journal, so status and browser setup keep working before any profile exists.
8. The setup review requires a human answer. An MCP session is always an agent's provider run, and the MCP service has no knowledge of which provider runs it, so no MCP session answers the review: MCP may start and observe a setup, and a person approves its download from the desktop, TUI or CLI.

## Implementation

We will register the four operations in an entrypoints composition group, with their access facts, result and review projections and phase codes. Then each surface becomes a client:
- The CLI submits through `run_registered_operation`, with a review handler that prompts or takes `--yes` and an event consumer drawing progress.
- The TUI uses the operation modal, which gains a progress row, and the setup door is deleted.
- MCP drops its four setup tools for the generic execute and observe tools; it never responds to the setup review.
- The repair report and the MCP setup gate read status through the status operation.

## Rationale

Only registered operations give status reads and the browser download the runtime admission, journal, review bearer and effect accounting that every other CLI, TUI and MCP submission has. The framework already holds the pieces, so the cost lies on the surfaces, not in a second mechanism.

## Consequences

- Setup and status gain admission, journaling and a durable review.
- Plan drift between review and apply becomes a visible refusal.
- Status reads become journaled operations, which costs time on frequently refreshed surfaces.
- The TUI modal and the CLI gain progress rendering, and MCP loses its special setup tools.
- Reconsider if a surface needs a status read that the operation's journaling makes too slow.
