---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8d1c79c58381655d9c1470b85a227ab1f4ab9a3536128c9e0ce4171a453d25eb'
step_id: 'S244'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Repair the main nitpicky API documentation cross-references and toctree ownership against current public module exports

## Scope

- `docs/api/ and docs/conf.py`

## Description

- Trace API-reference ownership through Vaultspec RAG and confirm the owning scaffold command and facade rules with targeted source search.
- Reconstruct the committed source tree in an isolated snapshot so active peer custody and registry changes cannot enter the result.
- Run the owning API scaffold generator against that snapshot and transfer only its generated additions, removals, and parent-toctree updates.
- Verify the regenerated snapshot has zero missing, orphaned, or stale API stubs and run the API-stub conformance tests.
- Attempt the mandatory full nitpicky build against the isolated snapshot and partition its source-docstring and autodoc failures from this generator-owned repair.
- Submit the scoped delta for an independent formal code review before closure.

## Outcome

The generated API reference now matches the public module tree at the committed baseline: 42 defining-module stubs were added, eight retired stubs were removed, and twelve owning parent toctrees were regenerated. The owning scaffold check reports no drift and its focused test suite passes.

## Notes

- During formal review, `_profile_custody` was found to have entered current HEAD after the first isolated snapshot. The reference was refreshed from the new HEAD and its defining-module stub and parent enrollment were added before re-review.
- The shared worktree contains concurrent uncommitted TUI-secret relocation work. Its missing, orphaned, and stale stubs were deliberately excluded because the defining source changes are not part of current HEAD or this step's ownership; the isolated committed snapshot remains conformant.
- The isolated full `-n -W` build reaches the regenerated API tree but remains red on broad pre-existing source docstring syntax, duplicate object descriptions, unresolved third-party/type-variable references, and mocked Pydantic serializer inspection. Representative failures occur in storage facade prose, aggregation internals, core result-disposition prose, and descendant-fact prose. Those defining source modules are outside this step's declared `docs/api/ and docs/conf.py` scope and were not swept into a repo-wide repair.
- No generated CLI reference page, private source module, or peer-owned source file was edited.
