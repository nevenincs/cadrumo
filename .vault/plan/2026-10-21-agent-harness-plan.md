---
tags:
  - '#plan'
  - '#agent-harness'
date: '2026-10-21'
tier: L1
related:
  - '[[2026-07-02-agent-harness-refoundation-adr]]'
modified: '2026-10-21'
body_schema: body-v2
body_hash: 'sha256:648f2aefd8d8cf074919f1b9e8e2382db8ca6f3423d5da9ef8725ad3e2eda0c6'
---

# `agent-harness` plan

Remove every piece of the agent harness from Cadrumo so that only the deterministic MCP service, the agent-key grant scope and the agent service host remain, matching the cadrumo-agent implementation.

## Description

Approved 2026-10-21. Basis: in session TUI-REFACTOR the user directed that tui carry none of the harness (skills, rules and the rest), that cadrumo-agent is its implementation, and that this work proceed without further approval gates ("go").

This is drift repair, not a new decision. cadrumo-agent's accepted `2026-10-15-agent-harness-adr` (cadrumo-agent vault) already rules that cadrumo-agent owns all authored agent content, its metadata, accessors, serving, provisioning and live persona evaluation, and that Cadrumo keeps only its tools, programs, MCP server and declarations. The 2026-10-21 boundary amendments to `2026-07-02-agent-harness-refoundation-adr` and the related Cadrumo ADRs bring this vault into line with that ruling; this plan implements them. No new ADR is involved.

Cadrumo keeps: the deterministic MCP service (`cadrumo-mcp`, package renamed to `src/cadrumo_mcp` in S05), its operation projection, discovery, search and operation-derived guidance, authority and corpus queries, runtime admission and cleanup, progress and diagnostics; the agent-key grant scope; `src/cadrumo_agent_service` as the host that launches the bundled cadrumo-agent and declares the MCP tool server through `CADRUMO_AGENT_TOOL_SERVER_<NAME>`; and deterministic MCP conformance in `dev/mcp_eval`. Cadrumo removes: `src/cadrumo_harness/_data/agent/**`, `_resources.py`, `resources.py`, `_skill_metadata.py`, `workspace.py`, `mcp/operating_layer.py` with `harness_load` and the `cadrumo://skill` and `cadrumo://rule` resources, the workspace materialisation flag, `dev/harness_data`, and the live persona parts of `dev/agent_eval`. The Claude Code plugin packaging was already removed in `e4188cc067`. No compatibility facade or duplicate definition remains.

The main worktree's uncommitted 2026-10-15 refactor came from a cadrumo-agent session working against the stale 2026-10-08 main base. It is reference material for intent only. Its base predates eleven MCP modules and `src/cadrumo_agent_service`, so it is never applied.

Open items carried from the amended ADRs, settled in implementation as follows. The command-operation reference generator leaves Cadrumo in S03; cadrumo-agent derives operation knowledge from MCP operation discovery. `applies_when` validation leaves Cadrumo in S03; cadrumo-agent's validator already takes a caller-supplied profile model. Porting Cadrumo-only content changes is S01. Provider policy in `src/cadrumo_agent_service` is out of scope here and stays with `2026-10-14-agent-service-boundary-plan`.

## Steps

- [x] `S01` - Port Cadrumo-only skill and rule changes made after the fork into cadrumo-agent and report files held by concurrent cadrumo-agent edits; `Y:/code/cadrumo-agent-worktrees/main/src/cadrumo_agent/harness/_data/agent`.
- [x] `S02` - Remove skill and rule serving from the MCP surface: operating layer, harness_load, cadrumo skill and rule resources, workspace flag and skill-loading tool descriptions; `src/cadrumo_harness/mcp`.
- [x] `S03` - Delete harness content and accessors with their tests, the command-operation reference generator and the wheel data include; `src/cadrumo_harness/_data, src/cadrumo_harness/resources.py, src/cadrumo_harness/workspace.py, dev/harness_data, pyproject.toml`.
- [x] `S04` - Reduce agent evaluation to deterministic MCP conformance in dev/mcp_eval, removing the live persona lane, scoring, flywheel, persona scenarios and eval-agent recipes; `dev/agent_eval, justfile`.
- [x] `S05` - Rename the package cadrumo_harness to cadrumo_mcp across code, packaging, import contracts, tooling and documentation; `src/cadrumo_harness, pyproject.toml, .importlinter, justfile, dev, docs`.
- [x] `S06` - Add a protective gate that rejects authored agent content and skill or rule serving in Cadrumo, proven against an isolated defect fixture; `dev/quality/tests`.
- [x] `S07` - Run import, style, format and type gates and the affected test suites, fixing every failure; `src, dev`.
- [x] `S08` - Save the main worktree's stale refactor to a side branch and put one squash commit of tui onto local main without pushing; `Y:/code/cadrumo-worktrees/main`.

## Parallelization

S01 runs in the cadrumo-agent repository and may run in parallel with S02 to S04. It must read the Cadrumo content before S03 deletes it, so it reads from commit `e4188cc067` instead of the working tree. S01 touches only cadrumo-agent files that no concurrent session has uncommitted edits in, and reports the rest. S02 to S07 touch the same package and run strictly in order under one executor. S08 runs last.

## Verification

- `git ls-files src dev` contains no path under `_data/agent`, no `SKILL.md`, and none of `resources.py`, `_skill_metadata.py`, `workspace.py` or `operating_layer.py` in the MCP package. `git grep` over `src` and `dev` finds no `harness_load`, `cadrumo://skill`, `cadrumo://rule` or `cadrumo_harness`, apart from the protective gate's own fixture strings.
- The S06 gate passes on the tree and fails on an isolated fixture that reintroduces a skill document and a skill-serving resource.
- `uv run --no-sync lint-imports --config .importlinter --no-cache`, `just check-style`, `just check-format` and `just check-types` exit 0.
- The `src/cadrumo_mcp`, `src/cadrumo_agent_service`, `dev/mcp_eval`, `dev/runtime_lifecycle` and `dev/packaging` test suites pass, and `cadrumo-mcp` still starts through its console script.
- After S08, local `main` is exactly one commit ahead of `origin/main`, and its tree equals tui's HEAD tree. The main worktree's 2026-10-15 refactor is preserved on its side branch.
- A final integrated review passes.
