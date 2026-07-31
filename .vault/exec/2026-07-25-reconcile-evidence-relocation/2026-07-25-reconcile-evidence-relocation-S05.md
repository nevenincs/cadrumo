---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:2f989aaa44cf0d4d69f28db44df0669e3fa683424dd8416f08c512ffc7e0f2b5'
step_id: 'S05'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Repoint list_modelo_reconciliations at the new store while keeping its return type so the CLI payload schema and the round-trip test are undisturbed, and delete diffs_detail from the payload rather than migrating it, leaving the event carrying verdict and count

## Scope

- `src/cadrumo/application/modelo/_reconcile.py`
- `src/cadrumo/entrypoints/cli/_modelo_reconcile_cli.py`

## Description

- Read the record store instead of the bucket-event catalogue, filtering to the bucket and optionally to one work unit.
- Sort oldest first by the reconciliation instant, breaking a tie on the event id so the listing is stable across reads.
- Project each record onto the existing history entry type, carrying the co-written event id through as the entry's event id.
- Delete the payload encoder and decoder outright, and drop the now-unused JSON import.

## Outcome

The return type is unchanged, so the history entry model, the CLI payload schema and the round-trip test that binds grounding across a persist-and-read-back cycle are all undisturbed. That test stayed green without being touched, which is what makes it a real gate on the relocation rather than a fixture to update.

The diff count is now derived from the stored diffs rather than parsed from a payload string, so the count and the detail cannot disagree.

The overflowing payload value is deleted rather than migrated, and no read path tolerates it. Nothing reads the retired field, and no compatibility branch was added.

## Notes

Storage order is the object-key digest order rather than the reconciliation order, so the sort is load-bearing rather than cosmetic; the tie-break on the event id keeps two runs sharing an instant in a stable order.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.
