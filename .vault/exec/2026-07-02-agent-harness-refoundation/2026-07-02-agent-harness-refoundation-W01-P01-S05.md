---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Extend the tool-descriptor tests for per-verb schemas, toolsets, and annotation coverage

## Scope

- `src/aeat/entrypoints/mcp/tests/test_tools_and_dispatch.py`

## Description

- Extend the tool-descriptor tests with a descriptor-level annotation-coverage assertion over the whole live descriptor set.
- Add a toolset-integration test asserting the five curated toolsets are non-empty and every grouped command key maps back to a real exposed descriptor, proving membership derives from the live surface.
- Complement the per-module unit tests added alongside S01 through S04 (`test_input_schema.py`, `test_toolsets.py`, `test_annotations.py`).

## Outcome

The mcp suite is green at 61 passed: every descriptor carries a non-bag per-verb schema equal to its structured projection, annotation coverage is total over the descriptor set, and toolset membership resolves entirely to real descriptors. Ruff check/format clean.

## Notes

Mid-step the shared worktree carried a peer's uncommitted wizard CLI (an untracked `_modelo_work_wizard_cli.py` plus an uncommitted `_modelo.py` import, neither on HEAD) whose parameter type Typer could not convert to click, which broke the entire `aeat app modelo` command tree and, transitively, the schema derivation my tests exercise. The breakage was confirmed to be peer WIP, not a HEAD regression (S01 through S04 were green against HEAD at 47/48/55/59 passed), and it cleared when the peer fixed the parameter type. No change to the feature was needed. The hard failure surfaced a design property worth noting: the schema build fails loudly if any CLI subtree is un-introspectable rather than silently shipping empty schemas, which is the honest behaviour for a console whose whole value is deep CLI knowledge.
