---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:16bb2ecf26014e8a98bd9d406b3daf65b1d9aa762db46615e850ed770b7f26e9'
step_id: 'S50'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Attach execution policy to modelo subtree callbacks and remove modelo risk path declarations

## Scope

- `src/cadrumo/entrypoints/cli/ modelo modules`

## Description

- Derive all modelo roots, groups, and leaves from the live command walker and attach immutable execution policy to each registered callback.
- Split policy shapes by actual registry, encrypted-fact, calculation, filing, browser, crypto, local-state, interactive, destructive, and write-route authority.
- Add the missing import-light crypto capability without implying custody and extend the taxonomy gate.
- Preserve help and bare invocation semantics for callbackless Typer groups by attaching inert callbacks.
- Add an exact live policy partition and planted unclassified, authority-downgrade, and route-downgrade tests.
- Retain the legacy keyed risk table only for its mandatory S52 consumer migration and complete deletion.
- Resolve every independent review finding and remove the final unused preset.

## Outcome

The live modelo subtree has complete callback-local policy coverage. Every registered node carries an explicit policy and no command path is inferred from the legacy risk table. Direct registry reads no longer acquire calculation or custody; local crypto verification no longer acquires profile custody; secure crypto reads and writes declare their actual encrypted-fact and route requirements; and the browser command declares browser and network effects without falsely declaring an AEAT live write.

Source enrollment landed in `b64e27f26c`; review-driven semantic corrections and exhaustive gates landed in `21fbf575e4`. The focused current-tree lane passed Ruff, ty, and 49 policy, taxonomy, and census tests. The feature-scoped Vaultspec check passed all sections.

## Notes

Shared-worktree commit `b64e27f26c` consumed the broad enrollment while review corrections were still in progress. No history was rewritten; the later exact-path correction commit preserves attribution for the final semantics. A plan-row phrase says to remove modelo risk declarations, but the operator's later explicit instruction and S52 migration contract require complete legacy-table deletion at S52. S50 therefore deliberately leaves that table unchanged and records the non-negotiable S52 deletion, including exports, consumers, and tests with no compatibility surface.
