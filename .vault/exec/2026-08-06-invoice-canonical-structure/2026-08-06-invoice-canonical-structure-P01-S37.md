---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9d1d501e619c43afd0093d3a3da1fa282d01d22e433792c1e81b219c355aae16'
step_id: 'S37'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Give the canonical invoice write paths the bucket lifecycle events the slim store emits, because the canonical creation, mutation and deletion paths emit no bucket event of any kind while the slim services emit six dedicated event types and return their ids in the operator mutation result, so repointing the bare verbs would drop the invoice audit trail and the bucket-event-ids field together, and deleting the slim store would orphan six enum members that then need consumer reconciliation

## Scope

- `src/cadrumo/application/invoices/_creation.py`

## Description

- Reused the existing bucket-event primitive and event vocabulary rather than introducing a canonical-only one.
- Chose the event type by invoice direction, mirroring the taxonomy the slim store used.
- Emitted after the persist, not before.
- Returned the event id on the creation result, matching the shape the slim mutation result gave the operator.
- Proved both directions, parametrised.

## Outcome

**The second and last blocking row on the conservation inventory is closed. `P03` is unblocked.**

The canonical write paths emitted no bucket event of any kind. The slim services emitted six dedicated types across create, update and remove, and returned their ids in the operator's mutation result. So repointing the operator's bare verbs onto the canonical store would have dropped the invoice audit trail and the event-ids field in a single change, and deleting the slim store would have removed the only emitter of six enum members — turning a deletion into an unplanned retired-enum reconciliation.

**This gap was named by no Step in the plan.** It surfaced while carrying the record-lifecycle timestamps: those and the events are one capability seen from two sides — what changed, and when — so closing only the field half would have left the audit story half-conserved. It was raised as its own Step and the conservation inventory then ruled it blocking.

Three choices in the implementation are deliberate:

- **The event type is chosen by DIRECTION**, so the canonical store speaks the vocabulary that already exists instead of minting a parallel one. Issued invoices are collectible, received ones payable. The six members therefore outlive the store that used to be their only emitter, which is what keeps the later deletion an ordinary deletion.
- **The event is emitted AFTER the save.** The reverse order would leave an event pointing at an invoice that never persisted, and that is worse than a missing event — a missing event is an absence, a dangling one reads as evidence.
- **The proof is parametrised over both directions.** A single-direction test would pass while the other half emitted the wrong event, which is precisely the silent mis-attribution this campaign has already found on three other axes.

The creation result now carries the emitted event ids, matching the shape the slim mutation result returned, so the operator surface loses nothing when the verbs are repointed.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices .../test_catalogue_invoice_lifecycle.py .../test_catalogue_invoice_wizard.py .../test_catalogue_invoice_link_flow.py -m "integration or unit" -q --no-header
    207 passed in 30.58s

    uv run --no-sync pytest src/cadrumo/application/ledger -q --no-header
    576 passed in 63.32s

    uv run --no-sync ruff check .../_creation.py .../test_creation.py
    All checks passed!

The ledger package is included deliberately: the evidence confirm boundary is one of the four production callers of the canonical creation primitive, so an emitter that failed to resolve its event repository there would have surfaced as a broad red rather than as a single test.

The proof resolves the returned event id against the persisted bucket history rather than asserting the function returned a string. An id that does not resolve is the failure this could plausibly have.

## Notes

**Scope: creation only.** The canonical surface has no update verb yet — that arrives when the bare verbs are repointed — and the delete path is a separate module. The updated and removed event types therefore remain unemitted on the canonical side, and the Step that repoints the operator verbs must carry them, or the audit trail will be complete for creation and silent for the other two mutations.

That is recorded here rather than left implicit, because a partially-emitting audit trail is the more dangerous state: an operator seeing creation events reasonably infers the absence of a removal event means no removal occurred.

**Both conservation blockers are now closed**, so the gate the inventory set no longer holds `P03` shut. The remaining `P01` Steps are proofs rather than gaps.
