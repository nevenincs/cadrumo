---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-07-31'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:cc804d9a25ec8b7be095b98157bb0c74e0f277018ce8d006c172aa2b7cd0ae98'
step_id: 'S01'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

# Report the collision between this ruling and the in-flight loader-hardening WIP to the coordinator and obtain an explicit handoff of the uncommitted changes before any deletion touches those files

## Scope

- `src/cadrumo/application/corpus_search/_model_loader.py`

## Description

- Identify the collision: an agent was implementing the 2026-07-31 audit hardening recommendation, holding uncommitted changes to `_model_loader.py`, `_embed_build.py`, `tests/test_query_embed.py`, and `pyproject.toml`.
- Confirm the ruling declines that recommendation as option O1, so the held work is overtaken rather than refuted.
- Determine that no revert is required: three of the four files are deletion targets of the P02 sweep, and the fourth carries a dependency addition to the `search` extra that the P03 sweep removes wholesale.
- Instruct the holding agent to stand down without editing, committing, reverting, or running any git operation, so no agent touches a working tree it does not own.
- Obtain explicit acknowledgement of the stand-down before dispatching the P02 implementer.

## Outcome

Handoff obtained. The holding agent acknowledged standing down on all five named paths with no action taken, leaving the tree as-is for the deletion sweep. No destructive git operation was run by any party, and no peer working-tree content was discarded. The P02 implementer was briefed that the uncommitted modifications on its deletion targets are released and are to be deleted with their files, and that `pyproject.toml` belongs to P03 and must be left untouched.

## Notes

The held work was correct against the audit recommendation it implemented and is overtaken by a scope decision, not by a defect. Its audit evidence — the silently dropped revision pin, the cache landing outside the app storage root, and the network round trip on every model load — is cited in the amending ADR's problem statement and contributed materially to the removal case.

One correction was issued during coordination and is recorded here because it touched the decision trail: a research finding was relayed as ruling generally against runtime semantic reuse when it in fact concerns the vaultspec-rag stack's own licence-encumbered and CUDA-bound models, which does not transfer to the MIT, CPU-only model in use here. The correction was issued before the ruling was finalised, and the ruling does not rest on that argument.
