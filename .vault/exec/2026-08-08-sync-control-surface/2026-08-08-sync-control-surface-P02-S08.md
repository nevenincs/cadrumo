---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:8513275f11c0ab93380f5c4b9cb23fe396bd3bc9fd0dce9cdaeb43d8608b0e39'
step_id: 'S08'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# REVERT the FiledRecaptureDivergence redeclaration introduced by P02.S02 at 86a9002581. The model at application/live/_remote_state_models.py:112 is a fifth carrier of a concept that already has a canonical home - CasillaDivergence at application/modelo/_reconcile_casilla.py:73 carries a typed CasillaId, a closed CasillaDivergenceKind, computed_value, filed_value and delta, whereas this one carries changed_casillas as a bare tuple of str with no values, no kind and no delta. It is not a different concept at a different granularity, it is the same concept carried worse and wrapped in filing identity. Three reasons revert rather than carry. First it has NO CONSUMER - P02.S03 is unbuilt, so this is a design-only shell of exactly the kind the architecture rule bars, because a shell accretes consumers before anyone re-examines it, and the dry-run short-circuit that is the real value of 86a9002581 does not depend on it. Second, the per-casilla comparator cluster is already unruled at four members on the synced-history-consumption plan, and arriving at that ruling with five, one of them strictly weaker, clarifies nothing. Third and load-bearing, reverting does NOT prejudge that ruling while folding WOULD. THIS ROW IS NOT A FOLD AND MUST NOT BE READ AS ONE - folding this carrier onto CasillaDivergence requires choosing between a comparator that returns bare strings with no tolerance and one that returns CasillaDivergence with a 0.01 default, which is precisely the open pair the other plan demands be ruled first, whereas removing a member is not choosing a comparator. Scope is therefore delete the model, delete its export from the application live facade, drop the recapture_divergences field from BulkFiledDataCaptureReport and from the capture accumulator, and keep both the dry_run short-circuit and the single-traversal shape of recapture_divergence_notices intact. Verified as a self-contained deletion rather than assumed - the only consumer is the report field this row also removes. Gate - the model and its facade export are gone, the dry-run short-circuit still returns a report and still writes nothing, the recapture advisory still fires on the notices channel unchanged, and no new carrier is introduced in its place

## Scope

- `src/cadrumo/application/live/_remote_state_models.py`
- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/application/live/__init__.py`

## Description

FOUND DELIVERED. This record was authored retroactively; no execution record
existed at delivery time, so the step was carried by its commit alone until
now.

- Delivered by `3612f729fa`, "remove the redeclared recapture divergence
  carrier".

## Outcome

Verified present at HEAD by reading, not by running:

- `rg -n "FiledRecaptureDivergence"` and `rg -n "recapture_divergences"` across
  `src/` both return no matches: the model, its facade export, and the
  `recapture_divergences` field on `BulkFiledDataCaptureReport` and the
  capture accumulator are gone.
- The dry-run short-circuit built by `P02.S02` is intact and unaffected: it
  still returns a report and still writes nothing.
- `recapture_divergence_notices` still runs as a single traversal and the
  advisory still fires on the `Notice` channel, unchanged.
- No new carrier replaces it: the divergence COUNT the sync-run record needs
  is answered by `len(accumulator.recapture_notices)` — the notices ARE the
  count, per the revert commit's own message.

The commit message additionally records that the row's own "no consumer"
premise was falsified before execution (the sync-run record, landed by
`P03.S01`/`P03.S02`, added a real consumer of the accumulator's divergence
list in between), and that the revert repointed that consumer onto the
notices list rather than the deleted model. See the retroactive row at
`P03.S09` for the fuller account of that drift and the lesson it carries.

## Notes

Nothing here was run. Every statement above is a source grep and a read at
HEAD; verification belongs to the gate owner.
