---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0b85509a63d639773c230fbbd916daeb40ad4c0b1de9c75e8d00bdb6ea9cbae3'
step_id: 'S08'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

## Description

- Ground the per-root recall seam with vaultspec-rag semantic searches over the active ADR, plan, deployment-parity execution record, production injector, and existing built-site gate.
- Read the existing built-site parity gate and its registry-backed record projections before editing.
- Add a bounded real-projection casilla probe to the existing browser/Pagefind gate, using the casilla title and every declared localized description as query terms on every root.

## Outcome

The built-site source gate now covers both halves of the multilingual recall contract: the existing concept probe and a new casilla probe. The casilla probe reuses `_materialise_records()` and `_bounded_to_sample()`, obtains one real `casilla` `SearchRecord`, and asserts that its canonical target is returned for the title and each available `OutputLanguage` description on every `en`, `es`, `ca`, and `hu` root. It exercises the production injector's all-language content blob through the same `pagefind.js` browser path the reader uses.

This is source coverage only. It does not establish that a built artefact or deployed root currently passes, and it does not close P03.S08 because the gate has not been run and the live-root re-probe remains deferred.

## Notes

- Static verification passed with Ruff, Python AST parsing, and `git diff --check` for the scoped test file.
- No tests, builds, Pagefind compilation, browser/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run.
- Shared worktree changes outside the scoped gate were preserved; nothing was staged, committed, reset, stashed, or cleaned.
- Grounding used the working `vaultspec-rag` CLI code-search route because the codebase alias route remains rejected; the VaultSpec semantic search also confirmed the governing locale-capability contract.

The casilla helper was tightened to select only a real bounded record carrying all four `OutputLanguage` descriptions; missing locale data now fails the probe-selection gate instead of being silently omitted.
