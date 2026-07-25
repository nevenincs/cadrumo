---
tags:
  - '#exec'
  - '#reconcile-evidence-relocation'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S07'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-plan]]"
---

# Rewrite the ModeloReconciliationHistoryEntry docstring whose no-parallel-reconciliation-store sentence the new store makes false, and re-affirm the provenance-carried constraint of the superseded Decision 2.B at the new site

## Scope

- `src/cadrumo/application/modelo/_reconcile.py`
- `.vault/adr/2026-07-01-reconcile-value-comparison-adr.md`

## Description

- Rewrite the history entry docstring, which asserted that no reconciliation was stored and that no parallel store existed.
- Re-affirm the stored-not-re-derived provenance constraint on the record model, with the reason it survives the move.
- Record the partial supersession on the governing decision record, naming what moves and what carries forward.
- Correct the reconcile module docstring, the history test module docstring, the CLI history help fallback and the CLI payload docstring, each of which asserted the same now-false thing.

## Outcome

No prose left standing asserts a guarantee the store makes false. A search of the source and documentation trees for the retired claims returns only unrelated matches in another lifecycle module.

The decision record now carries an explicit supersession note scoped to where the diff detail persists, and states what is unchanged: the typed divergence taxonomy, the requirement that a total or casilla divergence carry its legal and source references, the refusal of count-only history at the audit layer, and the derived diff count. The remaining decisions of that record are named as untouched.

The supersession note also records the measurement that made the move necessary, so a later reader does not have to reconstruct why a decision that shipped correctly stopped holding.

## Notes

The four locale catalogues needed no change. The now-false clause lived only in the English fallback in code; the translated leaves carry a shorter sentence that stays true. The catalogue drift check was run and is clean.

The frontmatter of the superseded decision record was left alone. Adding a backward related link would be a hand-edit of CLI-owned frontmatter, and the relocation record already names it in its own related field.

One factual basis in the governing relocation record is itself wrong, reported by the coordinator while this work was in flight and corrected by them on that record. The capped-payload shape is six occurrences, not the four the record tallies, and its conclusion that the pattern had resolved itself around the exception was false at the time it was written. Two further live instances sat in the ledger split and merge events, joining sixty-four character transaction ids and overflowing at exactly eight children — the same arithmetic as the attachment-removal instance, reproduced against the real model rather than estimated. Neither had ever been found.

This strengthens the relocation rather than qualifying it, and the direction is worth stating plainly because a later reader could take a larger tally as evidence against the exception. Every one of the five other instances was closable by bounded metadata, because in each the joined identifiers stay recoverable from their own catalogues; the split and merge payloads already carried the grouping id that keeps their cohort recoverable. Reconcile diff detail has no second home, which is why the same remedy is lossy here alone. That isolation is now demonstrated across six occurrences instead of asserted across four.

The stronger argument the correction supplies is about the guard rather than the tally: three independent passes each rediscovered this shape by accident, and two instances survived every one of them. That is the case for a standing gate, and it belongs to the separate systemic ruling rather than to this step.

Semantic discovery was unavailable for this work. The vaultspec-rag code index was truncated while reporting itself healthy, and three probes at 120, 300 and 600 second timeouts all expired with the service reporting itself degraded and one then three active index jobs. The service was not restarted. Every statement here rests on reading the owning packages and their exported surfaces directly, and on targeted pattern search against the current tree; a semantic miss would have proven nothing.

