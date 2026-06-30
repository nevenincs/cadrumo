---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S21'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W04.P08.S21 Live-Read Command Tree Mutation Guard

Scope: live AEAT read-only CLI command tree.

## Description

RAG grounding:

- `uvx vaultspec-rag search "live read command tree no submit mutation verbs justificante expediente portal" --type code`

The live command-tree structural guard was broadened from a short subgroup list to
the recursive live Typer tree. The guard now covers `filed`, `iva-wallet`,
`notifications`, `portals`, `expedientes`, `justificante`, `verify`, `borrador`,
and `borrador 100`, and rejects mutation-style command components including
`submit`, `send`, `present`, `sign`, `pay`, `push`, `modify`, `rectify`, `amend`,
`delete`, `cancel`, `acknowledge`, `accept`, `reject`, `file`, and `upload`.

## Outcome

Changed:

- `src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py`

Review found no correctness issues. Residual risk is exact-token matching only:
future synonyms must be added to the forbidden set or covered by a new guard.

## Verification

Passed:

- `uv run --no-sync pytest -p no:cacheprovider src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestReadOnlyStructuralInvariants -m "integration and hex_entrypoint" -q` -> 11 passed.
- Isolated latest-HEAD worktree with only W04 patch applied:
  `python -m pytest -p no:cacheprovider src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestReadOnlyStructuralInvariants -m "integration and hex_entrypoint" -q` -> 11 passed.
- W04 touched-file ruff gate in isolated latest-HEAD worktree passed.

