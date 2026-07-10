---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S03'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# Brief future code-fixer agents with required vaultspec-rag grounding and no-reexport/no-destructive-git constraints

## Scope

- `.vault/exec/2026-07-05-cpdefix-followup-allgreen/`

## Description

- Ground the future-worker brief in the campaign ADR, current blocker audit, counterpart-provider ADR, and shared-worktree safety rules.
- Record mandatory discovery, editing, verification, and closure constraints for any later code-fixer agent.
- Keep M720 and M347 stale-blocker classifications out of future code briefs unless a fresh gate fails.

## Outcome

Future code-fixer dispatches for this campaign must use this brief:

1. Start with RAG, then grep:
   `uv run --no-sync vaultspec-rag search "<concise task terms>" --type code --port 8766 --max-results 12 --timeout 30`
   and, when the task involves authority or intent:
   `uv run --no-sync vaultspec-rag search "<concise task terms>" --type vault --port 8766 --max-results 12 --timeout 30`.
   Read the top relevant source/record before editing, then pin exact symbols with `rg`.
2. Treat the shared worktree as active: inspect `git diff -- <file>` before first edit, do not revert unrelated WIP, and stage/commit only explicitly owned paths.
3. Never run destructive git commands. Do not use reset, checkout, clean, rebase, or stash as a shortcut.
4. Do not add fallback paths, shims, or reexports to pass a gate. Consume from real owning sources and existing public surfaces only.
5. Use real-behavior tests. Do not use fakes, mocks, stubs, monkeypatches, `skip`, `xfail`, or tautological expected values.
6. Preserve current blocker dispositions:
   - M720 row-carrier / `foreign_asset` enrollment is landed unless a fresh focused gate fails.
   - M347 summary support is invoice-owned.
   - Reserved counterpart provider enrollment remains gated by the accepted counterpart-provider ADR and requires the registry/provider/correctness gate to co-land.
7. Return changed file paths, commands run, and residual risks. Completed agents must be closed promptly.

No code-fixer agent was dispatched by this step; this is the standing dispatch contract for later live defects.

## Notes

- The user explicitly prohibited destructive git commands and reexport-style shortcuts during this campaign.
- The RAG service is healthy and should be used through `uv run --no-sync vaultspec-rag ... --port 8766`.
