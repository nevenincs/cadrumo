---
tags:
  - '#plan'
  - '#tui-all-mcp-integration'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
  - '[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]'
  - '[[2026-10-03-runtime-without-service-manager-adr]]'
  - '[[2026-07-08-mcp-progressive-discovery-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-10-03-application-packaging-interpreter-foundation-adr]]'
  - '[[2026-10-04-application-distribution-adr]]'
modified: '2026-10-04'
body_schema: body-v2
body_hash: 'sha256:1968093002008e671fbb93fd667090af82b6c413d3dec670544db6e5c5898185'
---

# `tui-all-mcp-integration` plan

## Description

Approved 2026-10-03

The user's current instruction explicitly authorizes integrating ALL missing MCP work, implementing conflicts, verification and review, and safely landing on feature/tui. Routine implementation needs no further permission. Preserve other writers' worktrees and original indexes.

Reconcile each snapshot against its original base, deduplicate intent, adapt it to current TUI modules, and record every source delta with evidence. The original inventory is .codex/handoffs/tui-all-mcp-20261003.json. Preserve later source states separately and inspect live destination drift before landing.

Decision coverage: the accepted MCP purpose and profile-access decisions govern exact-profile runtime operations and shared CLI/TUI/MCP admission; the accepted TUI architecture governs supervisor and receipt behavior. Progressive discovery governs S01 public corpus retrieval and ranked operation discovery. The accepted runtime-without-service-manager decision governs all Steps: transient worker containment remains required, while runtime management APIs, OS registration, autostart, repair and health controls remain excluded. Reuse these decisions unchanged; this integration makes no new costly commitment.

## Steps

- [x] `S01` - Restore public MCP corpus retrieval and ranked permitted-operation discovery; `src/cadrumo_harness/mcp, src/cadrumo/application/command_search, src/cadrumo/application/corpus_search`.
- [x] `S02` - Integrate missing native containment, peer identity, Darwin custody and filesystem primitives; `src/cadrumo/adapters/local_runtime, src/cadrumo/adapters/persistence/storage/custody, src/cadrumo/entrypoints/runtime`.
- [ ] `S03` - Reconcile broader MCP application, CLI, TUI, persistence and test-support changes; `src/cadrumo excluding S01 and S02 ownership`.
- [ ] `S04` - Account for every historical and later source delta and reconcile shared configuration and documentation; `.codex/handoffs/tui-all-mcp-*, dev, docs, conftest.py, pyproject.toml, justfile, env/.env.example`.
- [ ] `S05` - Verify and review combined interfaces and reconcile the live TUI destination before safe landing; `.vault/audit and integration verification corrections and landing evidence`.

## Parallelization

S01 (MCP discovery) and S04 historical source review are assigned to the history worker. S02 platform containment is assigned to the platform worker. S03 broader application/CLI/TUI/persistence changes are assigned to the baseline worker. They may run concurrently with disjoint source ownership supplied in dispatch. The supervisor owns all shared metadata, later snapshots, conftest/dev/config edits, plan, ledger and commits. Serialize Git and Vaultspec mutations. S05 combined verification, review and landing follows implementation and disposition reconciliation. The supervisor owns expensive or stateful checks; workers run only coordinated or independent focused checks.



## Verification

Account for every original and later source delta with incorporated commit, already-present evidence, superseded replacement/rationale, or a concrete unresolved reason. No conflict markers or obsolete management may enter product code. Run covering behavior/refusal tests, configured style/format/type/import-boundary checks and relevant CLI/TUI/MCP/runtime workflows. Native macOS acceptance is required for macOS containment claims; unavailable native infrastructure is a verification gap distinct from a code defect. Review the integrated result and retain pending gaps honestly. Close verified Steps only through owning verbs and make coherent provenance-bearing commits. Before safe landing reconcile later TUI commits and relevant working edits; an active writer prevents mutating their checkout without coordination.
